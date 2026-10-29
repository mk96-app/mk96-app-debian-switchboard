"""Módulo de red: listar y activar conexiones Wi-Fi guardadas vía NetworkManager (bus de sistema)."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

from mk96_app_debian_switchboard.dbus_utils import ServiceUnavailable, call_sync, get_proxy, set_property
from mk96_app_debian_switchboard.gtk_helpers import make_device_item, make_settings_item, notify_error
from mk96_app_debian_switchboard.radio_cycle import cycle_radio

NM_BUS_NAME = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
NM_IFACE = "org.freedesktop.NetworkManager"
NM_SETTINGS_PATH = "/org/freedesktop/NetworkManager/Settings"
NM_SETTINGS_IFACE = "org.freedesktop.NetworkManager.Settings"
NM_CONNECTION_IFACE = "org.freedesktop.NetworkManager.Settings.Connection"
NM_DEVICE_IFACE = "org.freedesktop.NetworkManager.Device"
NM_DEVICE_WIRELESS_IFACE = "org.freedesktop.NetworkManager.Device.Wireless"
NM_ACCESS_POINT_IFACE = "org.freedesktop.NetworkManager.AccessPoint"
NM_ACTIVE_CONNECTION_IFACE = "org.freedesktop.NetworkManager.Connection.Active"

WIFI_CONNECTION_TYPE = "802-11-wireless"
NM_DEVICE_TYPE_WIFI = 2

# org.freedesktop.NetworkManager.Connection.Active :: NMActiveConnectionState
NM_ACTIVE_CONNECTION_STATE_ACTIVATED = 2
NM_ACTIVE_CONNECTION_STATE_DEACTIVATED = 4

# org.freedesktop.NetworkManager.Connection.Active :: NMActiveConnectionStateReason
NM_REASON_NONE = 1
NM_REASON_USER_DISCONNECTED = 2
NM_REASON_LABELS = {
    3: "el dispositivo se desconectó",
    5: "configuración IP inválida",
    6: "tiempo de espera agotado",
    7: "tiempo de espera del servicio",
    8: "el servicio no pudo iniciar",
    9: "faltan credenciales (contraseña incorrecta o no guardada)",
    10: "fallo de autenticación",
    11: "la conexión fue eliminada",
    12: "dependencia fallida",
    13: "no se pudo inicializar el dispositivo",
    14: "el dispositivo fue eliminado",
}


def find_wifi_device_path(devices):
    """Lógica pura: ruta del primer dispositivo Wi-Fi de [(path, device_type)] (None si no hay)."""
    for path, device_type in devices:
        if device_type == NM_DEVICE_TYPE_WIFI:
            return path
    return None


def format_network_summary(active_ids, wifi_ids):
    """Lógica pura: resumen de estado para la etiqueta del grupo Conectividad: solo la
    Wi-Fi activa (las conexiones cableadas, puentes o docker no aportan)."""
    return ", ".join(sorted(set(active_ids) & set(wifi_ids))) or None


def format_connection_label(connection_id: str, is_active: bool) -> str:
    """Lógica pura: etiqueta del item de menú para una conexión Wi-Fi guardada."""
    prefix = "● " if is_active else "   "
    return f"{prefix}{connection_id}"


def is_wifi_connection(settings: dict) -> bool:
    """Lógica pura: True si el bloque 'connection' de settings es de tipo Wi-Fi."""
    return settings.get("connection", {}).get("type") == WIFI_CONNECTION_TYPE


def decode_ssid(ssid_bytes) -> str:
    """Lógica pura: decodifica el SSID (lista de bytes de D-Bus) a texto."""
    return bytes(ssid_bytes).decode("utf-8", errors="replace")


def extract_wifi_ssid(settings: dict) -> str | None:
    """Lógica pura: SSID de una conexión guardada, o None si no tiene."""
    ssid_bytes = settings.get("802-11-wireless", {}).get("ssid")
    if not ssid_bytes:
        return None
    return decode_ssid(ssid_bytes)


def is_activation_failure(state: int, reason: int) -> bool:
    """Lógica pura: True si un StateChanged de la conexión activa representa un fallo
    real de conexión (no una desconexión normal pedida por el usuario)."""
    if state != NM_ACTIVE_CONNECTION_STATE_DEACTIVATED:
        return False
    return reason not in (NM_REASON_NONE, NM_REASON_USER_DISCONNECTED)


def format_activation_error(connection_label: str, reason: int) -> str:
    """Lógica pura: mensaje de error legible para notificar un fallo de activación."""
    reason_text = NM_REASON_LABELS.get(reason, f"motivo desconocido ({reason})")
    return f"No se pudo conectar a {connection_label}: {reason_text}"


def filter_available_saved_connections(saved_connections: list, available_ssids: set) -> list:
    """Lógica pura: de las conexiones guardadas, solo las que están al alcance ahora.

    saved_connections: lista de (path, connection_id, ssid).
    """
    return [
        (path, connection_id)
        for path, connection_id, ssid in saved_connections
        if ssid in available_ssids
    ]


class NetworkModule:
    name = "Red wifi"
    group = "Conectividad"
    icon = "network-wireless-symbolic"

    def __init__(self, on_changed):
        self._on_changed = on_changed
        self._nm_proxy = None
        self._settings_proxy = None

    def _get_nm_proxy(self):
        if self._nm_proxy is None:
            self._nm_proxy = get_proxy(Gio.BusType.SYSTEM, NM_BUS_NAME, NM_PATH, NM_IFACE)
        return self._nm_proxy

    def _get_settings_proxy(self):
        if self._settings_proxy is None:
            self._settings_proxy = get_proxy(
                Gio.BusType.SYSTEM, NM_BUS_NAME, NM_SETTINGS_PATH, NM_SETTINGS_IFACE
            )
        return self._settings_proxy

    def is_available(self) -> bool:
        try:
            self._get_nm_proxy()
            return True
        except ServiceUnavailable:
            return False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def notify_changed(self) -> None:
        self._on_changed()

    def _active_connection_id(self):
        nm_proxy = self._get_nm_proxy()
        active_paths = nm_proxy.get_cached_property("ActiveConnections").unpack()
        active_ids = set()
        for path in active_paths:
            proxy = get_proxy(
                Gio.BusType.SYSTEM,
                NM_BUS_NAME,
                path,
                "org.freedesktop.NetworkManager.Connection.Active",
            )
            active_ids.add(proxy.get_cached_property("Id").unpack())
        return active_ids

    def _list_wifi_connections(self):
        """Devuelve (path, connection_id, ssid) de cada conexión Wi-Fi guardada."""
        settings_proxy = self._get_settings_proxy()
        result = call_sync(settings_proxy, "ListConnections")
        (connection_paths,) = result.unpack()
        wifi_connections = []
        for path in connection_paths:
            conn_proxy = get_proxy(
                Gio.BusType.SYSTEM, NM_BUS_NAME, path, NM_CONNECTION_IFACE
            )
            settings = call_sync(conn_proxy, "GetSettings").unpack()[0]
            if is_wifi_connection(settings):
                connection_id = settings["connection"]["id"]
                ssid = extract_wifi_ssid(settings)
                wifi_connections.append((path, connection_id, ssid))
        return wifi_connections

    def _list_available_ssids(self):
        """SSIDs actualmente en alcance (escaneados por el dispositivo Wi-Fi)."""
        nm_proxy = self._get_nm_proxy()
        (device_paths,) = call_sync(nm_proxy, "GetDevices").unpack()
        available_ssids = set()
        for device_path in device_paths:
            device_proxy = get_proxy(
                Gio.BusType.SYSTEM, NM_BUS_NAME, device_path, NM_DEVICE_IFACE
            )
            device_type = device_proxy.get_cached_property("DeviceType")
            if device_type is None or device_type.unpack() != NM_DEVICE_TYPE_WIFI:
                continue
            wireless_proxy = get_proxy(
                Gio.BusType.SYSTEM, NM_BUS_NAME, device_path, NM_DEVICE_WIRELESS_IFACE
            )
            access_points = wireless_proxy.get_cached_property("AccessPoints").unpack()
            for ap_path in access_points:
                ap_proxy = get_proxy(
                    Gio.BusType.SYSTEM, NM_BUS_NAME, ap_path, NM_ACCESS_POINT_IFACE
                )
                ssid_bytes = ap_proxy.get_cached_property("Ssid")
                if ssid_bytes is not None:
                    available_ssids.add(decode_ssid(ssid_bytes.unpack()))
        return available_ssids

    def _activate_connection(self, connection_path, connection_label):
        try:
            nm_proxy = self._get_nm_proxy()
            result = call_sync(
                nm_proxy,
                "ActivateConnection",
                GLib.Variant("(ooo)", (connection_path, "/", "/")),
            )
            (active_connection_path,) = result.unpack()
            self._watch_activation(active_connection_path, connection_label)
        except ServiceUnavailable as exc:
            notify_error("Red wifi", f"No se pudo conectar a {connection_label}: {exc}")
        self.notify_changed()

    def _wifi_device_path(self):
        (device_paths,) = call_sync(self._get_nm_proxy(), "GetDevices").unpack()
        devices = []
        for path in device_paths:
            device_type = get_proxy(
                Gio.BusType.SYSTEM, NM_BUS_NAME, path, NM_DEVICE_IFACE
            ).get_cached_property("DeviceType")
            devices.append((path, device_type.unpack() if device_type is not None else None))
        return find_wifi_device_path(devices)

    def _disconnect_wifi(self, connection_label):
        # Device.Disconnect (como `nmcli device disconnect`) evita que NetworkManager
        # vuelva a conectar solo al instante, a diferencia de DeactivateConnection.
        try:
            device_path = self._wifi_device_path()
            if device_path is None:
                raise ServiceUnavailable("no hay dispositivo Wi-Fi")
            device_proxy = get_proxy(Gio.BusType.SYSTEM, NM_BUS_NAME, device_path, NM_DEVICE_IFACE)
            call_sync(device_proxy, "Disconnect")
        except ServiceUnavailable as exc:
            notify_error("Red wifi", f"No se pudo desconectar de {connection_label}: {exc}")
        self.notify_changed()

    def _reconnect(self, connection_path, connection_label):
        """Apaga y enciende el Wi-Fi (corta toda la red unos segundos) y vuelve a
        conectar la red elegida."""

        def set_wifi_enabled(enabled: bool) -> None:
            set_property(
                Gio.BusType.SYSTEM, NM_BUS_NAME, NM_PATH, NM_IFACE,
                "WirelessEnabled", GLib.Variant("b", enabled),
            )

        cycle_radio(
            set_wifi_enabled,
            lambda: self._activate_connection(connection_path, connection_label),
            lambda exc: notify_error("Red wifi", f"No se pudo reconectar {connection_label}: {exc}"),
        )

    def _watch_activation(self, active_connection_path, connection_label):
        """NetworkManager.ActivateConnection devuelve casi al instante (solo confirma que
        empezó a intentarlo); el éxito o fallo real (contraseña incorrecta, fuera de
        alcance, timeout...) llega después vía la señal StateChanged de esta conexión
        activa, así que hay que escucharla para poder avisar del fallo."""
        proxy = get_proxy(
            Gio.BusType.SYSTEM, NM_BUS_NAME, active_connection_path, NM_ACTIVE_CONNECTION_IFACE
        )
        handler_id = None

        def on_signal(_proxy, _sender_name, signal_name, parameters):
            if signal_name != "StateChanged":
                return
            state, reason = parameters.unpack()
            if is_activation_failure(state, reason):
                notify_error("Red wifi", format_activation_error(connection_label, reason))
            if state in (
                NM_ACTIVE_CONNECTION_STATE_ACTIVATED,
                NM_ACTIVE_CONNECTION_STATE_DEACTIVATED,
            ):
                proxy.disconnect(handler_id)
                self.notify_changed()

        handler_id = proxy.connect("g-signal", on_signal)

    def summary(self):
        try:
            wifi_ids = {connection_id for _path, connection_id, _ssid in self._list_wifi_connections()}
            return format_network_summary(self._active_connection_id(), wifi_ids)
        except ServiceUnavailable:
            return None

    def build_menu_section(self) -> list:
        items = []
        try:
            active_ids = self._active_connection_id()
            available_ssids = self._list_available_ssids()
            saved_connections = self._list_wifi_connections()
            visible_connections = filter_available_saved_connections(
                saved_connections, available_ssids
            )
            for path, connection_id in visible_connections:
                is_active = connection_id in active_ids
                label = format_connection_label(connection_id, is_active)
                items.append(
                    make_device_item(
                        label,
                        is_active,
                        lambda p=path, cid=connection_id, a=is_active: (
                            self._disconnect_wifi(cid) if a else self._activate_connection(p, cid)
                        ),
                        lambda p=path, cid=connection_id: self._reconnect(p, cid),
                    )
                )
            if not visible_connections:
                item = Gtk.MenuItem(label="Ninguna red guardada al alcance")
                item.set_sensitive(False)
                items.append(item)
        except ServiceUnavailable:
            item = Gtk.MenuItem(label="Red wifi no disponible")
            item.set_sensitive(False)
            items.append(item)
        items.append(make_settings_item("wifi"))
        return items
