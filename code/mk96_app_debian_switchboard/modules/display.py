"""Módulo de pantalla: Night Light (Gio.Settings, esquema
org.gnome.settings-daemon.plugins.color)."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio

from mk96_app_debian_switchboard.gtk_helpers import make_checkbox_item, make_settings_item

COLOR_SCHEMA_ID = "org.gnome.settings-daemon.plugins.color"
NIGHT_LIGHT_KEY = "night-light-enabled"


def has_schema(schema_id: str) -> bool:
    """Lógica pura (dado el source): True si el esquema gsettings existe en este sistema."""
    return Gio.SettingsSchemaSource.get_default().lookup(schema_id, True) is not None


def format_display_summary(night_light_on: bool):
    """Lógica pura: resumen de estado para la etiqueta del grupo Pantalla."""
    return "Luz nocturna" if night_light_on else None


class DisplayModule:
    name = "Pantalla"
    group = "Pantalla"
    icon = "display-brightness-symbolic"

    def __init__(self, on_changed):
        self._on_changed = on_changed
        self._color_settings = None

    def _get_color_settings(self):
        if self._color_settings is None:
            self._color_settings = Gio.Settings.new(COLOR_SCHEMA_ID)
        return self._color_settings

    def is_available(self) -> bool:
        return has_schema(COLOR_SCHEMA_ID)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def notify_changed(self) -> None:
        self._on_changed()

    def _set_night_light(self, new_state: bool) -> None:
        self._get_color_settings().set_boolean(NIGHT_LIGHT_KEY, new_state)
        self.notify_changed()

    def summary(self):
        return format_display_summary(self._get_color_settings().get_boolean(NIGHT_LIGHT_KEY))

    def build_menu_section(self) -> list:
        night_light_on = self._get_color_settings().get_boolean(NIGHT_LIGHT_KEY)
        return [
            make_checkbox_item("Luz nocturna", night_light_on, self._set_night_light),
            make_settings_item("display"),
        ]
