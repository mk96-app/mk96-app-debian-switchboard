"""Helpers finos sobre Gio.DBusProxy para bus de sesión y de sistema."""

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib


class ServiceUnavailable(Exception):
    """El servicio D-Bus solicitado no responde o no existe."""


def get_proxy(bus_type, bus_name, object_path, interface_name):
    """Crea un Gio.DBusProxy síncrono. Lanza ServiceUnavailable si falla."""
    try:
        return Gio.DBusProxy.new_for_bus_sync(
            bus_type,
            Gio.DBusProxyFlags.NONE,
            None,
            bus_name,
            object_path,
            interface_name,
            None,
        )
    except GLib.Error as exc:
        raise ServiceUnavailable(f"{interface_name} en {object_path}: {exc}") from exc


def call_sync(proxy, method_name, parameters=None, timeout_msec=3000):
    """Llama a un método D-Bus síncronamente. Traduce errores GLib a ServiceUnavailable."""
    try:
        return proxy.call_sync(
            method_name, parameters, Gio.DBusCallFlags.NONE, timeout_msec, None
        )
    except GLib.Error as exc:
        raise ServiceUnavailable(f"{method_name}: {exc}") from exc


def set_property(bus_type, bus_name, object_path, interface_name, property_name, value_variant):
    """Cambia una propiedad D-Bus de verdad (org.freedesktop.DBus.Properties.Set).

    Gio.DBusProxy.set_cached_property NO hace esto: solo actualiza la caché local del
    proxy, sin avisar al servicio remoto. Para que el cambio se aplique en el sistema
    real hay que llamar a Properties.Set explícitamente.
    """
    props_proxy = get_proxy(bus_type, bus_name, object_path, "org.freedesktop.DBus.Properties")
    call_sync(
        props_proxy,
        "Set",
        GLib.Variant("(ssv)", (interface_name, property_name, value_variant)),
    )


def subscribe_properties_changed(proxy, callback):
    """Suscribe callback(changed_properties: dict) a la señal PropertiesChanged del proxy."""

    def _on_signal(_proxy, changed_properties, _invalidated_properties):
        callback(changed_properties.unpack())

    return proxy.connect("g-properties-changed", _on_signal)
