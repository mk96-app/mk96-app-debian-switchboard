"""Helpers de UI compartidos por todos los módulos: items de menú de acción, notificaciones
de error y acceso directo a los paneles de Ajustes de GNOME.

Nota de arquitectura: AppIndicator no dibuja el menú en este proceso. Lo exporta por D-Bus
(protocolo com.canonical.dbusmenu) y es GNOME Shell quien lo reconstruye y lo muestra; al
hacer click, Shell llama de vuelta a `Event(id, "clicked", ...)`, y libdbusmenu-gtk traduce
eso en emitir la señal 'activate' del Gtk.MenuItem original en este proceso. Por eso los
items de acción TIENEN que ser Gtk.MenuItem normales conectados a 'activate' -cualquier
otro widget/señal (Gtk.Button + 'clicked', 'button-release-event', etc.) no llega a
dispararse nunca, porque ese evento real de ratón ocurre en el proceso de GNOME Shell, no
aquí. Por la misma razón, tampoco hay forma de evitar que el menú se cierre al seleccionar
un item: quien decide cerrarlo es GNOME Shell, no este código.
"""

import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

from mk96_app_debian_switchboard.dbus_utils import ServiceUnavailable, call_sync, get_proxy

NOTIFICATIONS_BUS_NAME = "org.freedesktop.Notifications"
NOTIFICATIONS_PATH = "/org/freedesktop/Notifications"
NOTIFICATIONS_IFACE = "org.freedesktop.Notifications"


def make_action_item(label: str, callback) -> Gtk.MenuItem:
    """Item de menú de acción: Gtk.MenuItem normal conectado a 'activate' (la única señal
    que GNOME Shell realmente dispara para un item de AppIndicator; ver nota del módulo)."""
    item = Gtk.MenuItem(label=label)
    item.connect("activate", lambda _widget: callback())
    return item


def make_checkbox_item(label: str, is_checked: bool, callback) -> Gtk.CheckMenuItem:
    """Item de menú tipo checkbox. `callback(new_state: bool)` se llama con el estado
    ya invertido (Gtk.CheckMenuItem cambia su propio 'active' antes de emitir 'toggled').
    El checkbox es un tipo de item estándar del protocolo dbusmenu (toggle-type/
    toggle-state), así que GNOME Shell sí sabe dibujarlo correctamente.
    """
    item = Gtk.CheckMenuItem(label=label)
    item.set_active(is_checked)
    item.connect("toggled", lambda widget: callback(widget.get_active()))
    return item


def device_action_labels(is_connected: bool) -> tuple:
    """Lógica pura: acciones del submenú de un dispositivo/red según su estado."""
    return ("Desconectar" if is_connected else "Conectar", "Reconectar")


def make_device_item(label: str, is_connected: bool, on_toggle, on_reconnect) -> Gtk.MenuItem:
    """Item de un dispositivo/red con submenú Conectar|Desconectar + Reconectar."""
    toggle_label, reconnect_label = device_action_labels(is_connected)
    submenu = Gtk.Menu()
    submenu.append(make_action_item(toggle_label, on_toggle))
    submenu.append(make_action_item(reconnect_label, on_reconnect))
    item = Gtk.MenuItem(label=label)
    item.set_submenu(submenu)
    return item


def make_settings_item(panel_name: str) -> Gtk.MenuItem:
    """Item de menú que abre el panel correspondiente de GNOME Settings."""
    return make_action_item(
        "Abrir ajustes...", lambda: open_settings_panel(panel_name)
    )


def open_settings_panel(panel_name: str) -> None:
    subprocess.Popen(["gnome-control-center", panel_name])


def notify_error(summary: str, body: str) -> None:
    """Notificación de escritorio best-effort; si el servicio no responde, no hace nada
    (no tiene sentido que un fallo al notificar un error tire la app)."""
    try:
        proxy = get_proxy(
            Gio.BusType.SESSION,
            NOTIFICATIONS_BUS_NAME,
            NOTIFICATIONS_PATH,
            NOTIFICATIONS_IFACE,
        )
        call_sync(
            proxy,
            "Notify",
            GLib.Variant(
                "(susssasa{sv}i)",
                ("MK96 Debian Switchboard", 0, "dialog-error", summary, body, [], {}, 5000),
            ),
        )
    except ServiceUnavailable:
        pass
