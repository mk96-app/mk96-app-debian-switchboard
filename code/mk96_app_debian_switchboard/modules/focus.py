"""Módulo de No Molestar: silencia los banners de notificación (Gio.Settings, esquema
org.gnome.desktop.notifications). Es el mismo interruptor que usa el "No molestar" nativo
de los ajustes rápidos de GNOME.
"""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio

from mk96_app_debian_switchboard.gtk_helpers import make_checkbox_item, make_settings_item
from mk96_app_debian_switchboard.modules.display import has_schema

NOTIFICATIONS_SCHEMA_ID = "org.gnome.desktop.notifications"
SHOW_BANNERS_KEY = "show-banners"


def is_dnd_enabled(show_banners: bool) -> bool:
    """Lógica pura: 'No molestar' está activo cuando los banners están desactivados."""
    return not show_banners


def format_focus_summary(dnd_enabled: bool):
    """Lógica pura: resumen de estado para la etiqueta del grupo Pantalla."""
    return "No molestar" if dnd_enabled else None


class FocusModule:
    name = "No molestar"
    group = "Pantalla"
    icon = "notifications-disabled-symbolic"

    def __init__(self, on_changed):
        self._on_changed = on_changed
        self._settings = None

    def _get_settings(self):
        if self._settings is None:
            self._settings = Gio.Settings.new(NOTIFICATIONS_SCHEMA_ID)
        return self._settings

    def is_available(self) -> bool:
        return has_schema(NOTIFICATIONS_SCHEMA_ID)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def notify_changed(self) -> None:
        self._on_changed()

    def _set_dnd(self, dnd_enabled: bool) -> None:
        # "No molestar" activado == banners desactivados.
        self._get_settings().set_boolean(SHOW_BANNERS_KEY, not dnd_enabled)
        self.notify_changed()

    def summary(self):
        return format_focus_summary(
            is_dnd_enabled(self._get_settings().get_boolean(SHOW_BANNERS_KEY))
        )

    def build_menu_section(self) -> list:
        dnd_enabled = is_dnd_enabled(self._get_settings().get_boolean(SHOW_BANNERS_KEY))
        return [
            make_checkbox_item("Activar no molestar", dnd_enabled, self._set_dnd),
            make_settings_item("notifications"),
        ]
