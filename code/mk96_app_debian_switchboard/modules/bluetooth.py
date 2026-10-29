"""Módulo de bluetooth: listar/conectar dispositivos ya emparejados vía BlueZ (bus de sistema)."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

from mk96_app_debian_switchboard.dbus_utils import ServiceUnavailable, call_sync, get_proxy, set_property
from mk96_app_debian_switchboard.gtk_helpers import make_device_item, make_settings_item, notify_error
from mk96_app_debian_switchboard.radio_cycle import cycle_radio

BLUEZ_BUS_NAME = "org.bluez"
OBJECT_MANAGER_PATH = "/"
OBJECT_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"
DEVICE_IFACE = "org.bluez.Device1"
ADAPTER_IFACE = "org.bluez.Adapter1"
# Connect() puede tardar varios segundos en negociar con el dispositivo real.
CONNECT_TIMEOUT_MSEC = 15000


def format_device_label(name: str, is_connected: bool) -> str:
    """Lógica pura: etiqueta del item de menú para un dispositivo bluetooth emparejado."""
    prefix = "● " if is_connected else "   "
    return f"{prefix}{name}"


def find_adapter_path(managed_objects: dict):
    """Lógica pura: ruta del primer adaptador Bluetooth (None si no hay ninguno)."""
    for path, interfaces in managed_objects.items():
        if ADAPTER_IFACE in interfaces:
            return path
    return None


def extract_paired_devices(managed_objects: dict) -> list:
    """Lógica pura: filtra el resultado de GetManagedObjects a solo dispositivos emparejados.

    Devuelve lista de tuplas (path, name, is_connected).
    """
    devices = []
    for path, interfaces in managed_objects.items():
        device_props = interfaces.get(DEVICE_IFACE)
        if device_props is None:
            continue
        if not device_props.get("Paired", False):
            continue
        name = device_props.get("Name", device_props.get("Address", path))
        is_connected = device_props.get("Connected", False)
        devices.append((path, name, is_connected))
    return devices


def format_bluetooth_summary(connected_count: int):
    """Lógica pura: resumen de estado para la etiqueta del grupo Conectividad."""
    return f"{connected_count} Bluetooth" if connected_count else None


class BluetoothModule:
    name = "Bluetooth"
    group = "Conectividad"
    icon = "bluetooth-active-symbolic"

    def __init__(self, on_changed):
        self._on_changed = on_changed
        self._object_manager_proxy = None

    def _get_object_manager_proxy(self):
        if self._object_manager_proxy is None:
            self._object_manager_proxy = get_proxy(
                Gio.BusType.SYSTEM,
                BLUEZ_BUS_NAME,
                OBJECT_MANAGER_PATH,
                OBJECT_MANAGER_IFACE,
            )
        return self._object_manager_proxy

    def is_available(self) -> bool:
        try:
            self._get_object_manager_proxy()
            return True
        except ServiceUnavailable:
            return False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def notify_changed(self) -> None:
        self._on_changed()

    def _get_managed_objects(self):
        proxy = self._get_object_manager_proxy()
        (managed_objects,) = call_sync(proxy, "GetManagedObjects").unpack()
        return managed_objects

    def _toggle_connection(self, device_path, device_name, is_connected):
        device_proxy = get_proxy(
            Gio.BusType.SYSTEM, BLUEZ_BUS_NAME, device_path, DEVICE_IFACE
        )
        action = "Disconnect" if is_connected else "Connect"
        try:
            call_sync(device_proxy, action, timeout_msec=CONNECT_TIMEOUT_MSEC)
        except ServiceUnavailable as exc:
            verb = "desconectar" if is_connected else "conectar"
            notify_error("Bluetooth", f"No se pudo {verb} {device_name}: {exc}")
        self.notify_changed()

    def _reconnect(self, device_path, device_name):
        """Apaga y enciende el adaptador (afecta a todos los dispositivos Bluetooth) y
        vuelve a conectar el dispositivo elegido."""
        try:
            adapter_path = find_adapter_path(self._get_managed_objects())
        except ServiceUnavailable as exc:
            notify_error("Bluetooth", f"No se pudo reconectar {device_name}: {exc}")
            return
        if adapter_path is None:
            notify_error("Bluetooth", f"No se pudo reconectar {device_name}: no hay adaptador")
            return

        def set_powered(powered: bool) -> None:
            set_property(
                Gio.BusType.SYSTEM, BLUEZ_BUS_NAME, adapter_path, ADAPTER_IFACE,
                "Powered", GLib.Variant("b", powered),
            )

        cycle_radio(
            set_powered,
            lambda: self._toggle_connection(device_path, device_name, False),
            lambda exc: notify_error("Bluetooth", f"No se pudo reconectar {device_name}: {exc}"),
        )

    def summary(self):
        try:
            devices = extract_paired_devices(self._get_managed_objects())
        except ServiceUnavailable:
            return None
        return format_bluetooth_summary(sum(1 for _p, _n, connected in devices if connected))

    def build_menu_section(self) -> list:
        items = []
        try:
            managed_objects = self._get_managed_objects()
            for path, name, is_connected in extract_paired_devices(managed_objects):
                label = format_device_label(name, is_connected)
                items.append(
                    make_device_item(
                        label,
                        is_connected,
                        lambda p=path, n=name, c=is_connected: self._toggle_connection(p, n, c),
                        lambda p=path, n=name: self._reconnect(p, n),
                    )
                )
        except ServiceUnavailable:
            item = Gtk.MenuItem(label="Bluetooth no disponible")
            item.set_sensitive(False)
            items.append(item)
        items.append(make_settings_item("bluetooth"))
        return items
