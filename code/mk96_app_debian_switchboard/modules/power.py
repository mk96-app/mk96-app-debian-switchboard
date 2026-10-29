"""Módulo de energía: perfil (power-profiles-daemon) y batería (UPower). Bus de sistema."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

from mk96_app_debian_switchboard.dbus_utils import ServiceUnavailable, get_proxy, set_property
from mk96_app_debian_switchboard.gtk_helpers import make_action_item, make_settings_item, notify_error

PROFILES_BUS_NAME = "net.hadess.PowerProfiles"
PROFILES_PATH = "/net/hadess/PowerProfiles"
PROFILES_IFACE = "net.hadess.PowerProfiles"

UPOWER_BUS_NAME = "org.freedesktop.UPower"
UPOWER_PATH = "/org/freedesktop/UPower/devices/DisplayDevice"
UPOWER_IFACE = "org.freedesktop.UPower.Device"

PROFILE_LABELS = {
    "power-saver": "Ahorro de energía",
    "balanced": "Equilibrado",
    "performance": "Rendimiento",
}


def format_profile_label(profile_id: str, is_active: bool) -> str:
    """Lógica pura: etiqueta del item de menú para un perfil de energía."""
    prefix = "● " if is_active else "   "
    label = PROFILE_LABELS.get(profile_id, profile_id)
    return f"{prefix}{label}"


def format_battery_label(percentage: float, state: int) -> str:
    """Lógica pura: etiqueta de solo lectura con el estado de batería.

    state sigue el enum UPower.Device.State: 1=Charging, 2=Discharging, 4=FullyCharged.
    """
    state_text = {1: "cargando", 2: "en uso", 4: "completa"}.get(state, "desconocido")
    return f"Batería: {round(percentage)}% ({state_text})"


def format_power_summary(profile_id, percentage):
    """Lógica pura: resumen de estado para la etiqueta del grupo Energía
    (perfil activo y batería; cualquiera de los dos puede faltar)."""
    parts = []
    if profile_id:
        parts.append(PROFILE_LABELS.get(profile_id, profile_id))
    if percentage is not None:
        parts.append(f"{round(percentage)}%")
    return " · ".join(parts) or None


class PowerModule:
    name = "Energía"
    group = "Energía"
    icon = "battery-good-symbolic"

    def __init__(self, on_changed):
        self._on_changed = on_changed
        self._profiles_proxy = None
        self._battery_proxy = None

    def _get_profiles_proxy(self):
        if self._profiles_proxy is None:
            self._profiles_proxy = get_proxy(
                Gio.BusType.SYSTEM, PROFILES_BUS_NAME, PROFILES_PATH, PROFILES_IFACE
            )
        return self._profiles_proxy

    def _get_battery_proxy(self):
        if self._battery_proxy is None:
            self._battery_proxy = get_proxy(
                Gio.BusType.SYSTEM, UPOWER_BUS_NAME, UPOWER_PATH, UPOWER_IFACE
            )
        return self._battery_proxy

    def is_available(self) -> bool:
        try:
            self._get_profiles_proxy()
            return True
        except ServiceUnavailable:
            return False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def notify_changed(self) -> None:
        self._on_changed()

    def _set_active_profile(self, profile_id, profile_label):
        try:
            set_property(
                Gio.BusType.SYSTEM,
                PROFILES_BUS_NAME,
                PROFILES_PATH,
                PROFILES_IFACE,
                "ActiveProfile",
                GLib.Variant("s", profile_id),
            )
        except ServiceUnavailable as exc:
            notify_error("Energía", f"No se pudo activar el perfil {profile_label}: {exc}")
        self.notify_changed()

    def summary(self):
        profile_id = percentage = None
        try:
            profile_id = self._get_profiles_proxy().get_cached_property("ActiveProfile").unpack()
        except ServiceUnavailable:
            pass
        try:
            percentage = self._get_battery_proxy().get_cached_property("Percentage").unpack()
        except ServiceUnavailable:
            pass
        return format_power_summary(profile_id, percentage)

    def build_menu_section(self) -> list:
        items = []
        try:
            profiles_proxy = self._get_profiles_proxy()
            active_profile = profiles_proxy.get_cached_property("ActiveProfile").unpack()
            profiles = profiles_proxy.get_cached_property("Profiles").unpack()
            for profile in profiles:
                profile_id = profile["Profile"]
                label = format_profile_label(profile_id, profile_id == active_profile)
                items.append(
                    make_action_item(
                        label,
                        lambda pid=profile_id, lbl=label: self._set_active_profile(pid, lbl),
                    )
                )
        except ServiceUnavailable:
            item = Gtk.MenuItem(label="Perfiles de energía no disponibles")
            item.set_sensitive(False)
            items.append(item)

        try:
            battery_proxy = self._get_battery_proxy()
            percentage = battery_proxy.get_cached_property("Percentage").unpack()
            state = battery_proxy.get_cached_property("State").unpack()
            battery_item = Gtk.MenuItem(label=format_battery_label(percentage, state))
            battery_item.set_sensitive(False)
            items.append(battery_item)
        except ServiceUnavailable:
            pass

        items.append(make_settings_item("power"))
        return items
