"""Módulo de audio: cambiar salida por defecto y ver volumen, vía `pactl` (PipeWire/PulseAudio).

Nota de implementación: se probó primero la interfaz D-Bus org.PulseAudio1 (bus de sesión,
sin polkit) pero en el sistema real no implementa org.freedesktop.DBus.Properties de forma
estándar (ni Introspectable), así que Gio.DBusProxy no puede cachear sus propiedades. `pactl`
sí es estable y soporta salida JSON (`pactl -f json ...`), así que se usa como backend real.
"""

import json
import os
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from mk96_app_debian_switchboard.gtk_helpers import (
    make_action_item,
    make_checkbox_item,
    make_settings_item,
    notify_error,
)
from mk96_app_debian_switchboard.pa_events import PulseEvents


def format_device_label(description: str, is_default: bool) -> str:
    """Lógica pura: etiqueta de un item de menú para un sink."""
    prefix = "● " if is_default else "   "
    return f"{prefix}{description}"


def parse_volume_percent(volume_percent: str) -> int:
    """Lógica pura: convierte '100%' (formato de `pactl -f json`) a 100."""
    return int(volume_percent.rstrip("%"))


def _find_active_port(sink: dict):
    active_port_name = sink.get("active_port")
    for port in sink.get("ports", []):
        if port["name"] == active_port_name:
            return port
    return None


def is_sink_usable(sink: dict) -> bool:
    """Lógica pura: False si el puerto activo del sink existe pero está marcado
    'not available' (ej. un puerto HDMI/DisplayPort sin monitor conectado)."""
    port = _find_active_port(sink)
    if port is None:
        return True
    return port.get("availability") != "not available"


def resolve_description(sink: dict) -> str:
    """Lógica pura: descripción legible del sink.

    Algunos dispositivos (ej. dongles USB en perfil digital/iec958) devuelven el string
    literal '(null)' como descripción en `pactl -f json`. En ese caso se construye un
    nombre a partir de las propiedades del dispositivo y el puerto activo.
    """
    description = sink.get("description") or ""
    if description and description != "(null)":
        return description

    properties = sink.get("properties", {})
    fallback_name = properties.get("device.product.name") or properties.get("alsa.card_name")
    port = _find_active_port(sink)
    port_description = port["description"] if port else None

    if fallback_name and port_description:
        return f"{fallback_name} ({port_description})"
    return fallback_name or port_description or sink.get("name", "Salida desconocida")


def format_audio_summary(volume_percent: int, muted: bool) -> str:
    """Lógica pura: resumen de estado para la etiqueta del grupo Audio."""
    return "Silenciado" if muted else f"{volume_percent}%"


def parse_mute_status(pactl_output: str) -> bool:
    """Lógica pura: 'Mute: yes'/'Mute: no' (salida de `pactl get-sink-mute`/
    `get-source-mute`) a bool."""
    return pactl_output.strip().rsplit(" ", 1)[-1] == "yes"


def parse_sinks(pactl_json_output: str) -> list:
    """Lógica pura: extrae (name, description) de sinks usables de `pactl list sinks`."""
    sinks = json.loads(pactl_json_output)
    return [
        (sink["name"], resolve_description(sink))
        for sink in sinks
        if is_sink_usable(sink)
    ]


class PactlError(Exception):
    """`pactl` no está disponible o devolvió un error."""


def run_pactl(*args: str) -> str:
    # LC_ALL=C evita que `pactl -f json` emita números con coma decimal (locale es_ES),
    # lo que rompe el parseo JSON estándar.
    env = {**os.environ, "LC_ALL": "C"}
    try:
        result = subprocess.run(
            ["pactl", *args],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
            env=env,
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise PactlError(str(exc)) from exc


class AudioModule:
    name = "Salida de audio"
    group = "Audio"
    icon = "audio-speakers-symbolic"

    def __init__(self, on_changed):
        self._on_changed = on_changed
        self._audio_panel = None
        self._events = None

    def _get_audio_panel(self):
        # Import diferido: audio_panel.py importa de este módulo (run_pactl, etc.), así
        # que importarlo aquí arriba crearía un ciclo de imports.
        if self._audio_panel is None:
            from mk96_app_debian_switchboard.audio_panel import AudioPanel

            self._audio_panel = AudioPanel()
        return self._audio_panel

    def is_available(self) -> bool:
        try:
            run_pactl("info")
            return True
        except PactlError:
            return False

    def start(self) -> None:
        self._events = PulseEvents(self.notify_changed, self._refresh_panel)
        self._events.start()

    def stop(self) -> None:
        if self._events is not None:
            self._events.stop()
            self._events = None

    def _refresh_panel(self) -> None:
        if self._audio_panel is not None:
            self._audio_panel.refresh()

    def notify_changed(self) -> None:
        self._on_changed()

    def _set_default_sink(self, sink_name: str, description: str) -> None:
        try:
            run_pactl("set-default-sink", sink_name)
        except PactlError as exc:
            notify_error("Salida de audio", f"No se pudo cambiar a {description}: {exc}")
        self.notify_changed()

    def _set_output_mute(self, _new_state: bool) -> None:
        try:
            run_pactl("set-sink-mute", "@DEFAULT_SINK@", "toggle")
        except PactlError as exc:
            notify_error("Salida de audio", f"No se pudo silenciar la salida: {exc}")
        self.notify_changed()

    def _set_mic_mute(self, _new_state: bool) -> None:
        try:
            run_pactl("set-source-mute", "@DEFAULT_SOURCE@", "toggle")
        except PactlError as exc:
            notify_error("Salida de audio", f"No se pudo silenciar el micrófono: {exc}")
        self.notify_changed()

    def summary(self):
        # Import diferido por el mismo ciclo que _get_audio_panel.
        from mk96_app_debian_switchboard.audio_panel import parse_get_volume_output

        try:
            muted = parse_mute_status(run_pactl("get-sink-mute", "@DEFAULT_SINK@"))
            volume = parse_get_volume_output(run_pactl("get-sink-volume", "@DEFAULT_SINK@"))
        except (PactlError, IndexError, ValueError):
            return None
        return format_audio_summary(volume, muted)

    def build_menu_section(self) -> list:
        # El mixer por app (futuro) usa subcomandos distintos a los de aquí abajo:
        # `set-sink-input-volume <index>` / `set-sink-input-mute <index>` sobre cada
        # entrada de `pactl list sink-inputs`, no `set-sink-volume`/`set-sink-mute` (esos
        # actúan sobre el dispositivo por defecto). Ya implementado en audio_panel.py.
        items = []
        items.append(
            make_action_item("Abrir panel de audio...", lambda: self._get_audio_panel().show())
        )
        items.append(Gtk.SeparatorMenuItem())

        try:
            output_muted = parse_mute_status(run_pactl("get-sink-mute", "@DEFAULT_SINK@"))
            items.append(make_checkbox_item("Silenciar salida", output_muted, self._set_output_mute))
            mic_muted = parse_mute_status(run_pactl("get-source-mute", "@DEFAULT_SOURCE@"))
            items.append(make_checkbox_item("Silenciar micrófono", mic_muted, self._set_mic_mute))
        except PactlError:
            pass

        try:
            sinks = parse_sinks(run_pactl("-f", "json", "list", "sinks"))
            default_sink = run_pactl("get-default-sink").strip()
            items.append(Gtk.SeparatorMenuItem())
            for sink_name, description in sinks:
                label = format_device_label(description, sink_name == default_sink)
                items.append(
                    make_action_item(
                        label,
                        lambda name=sink_name, desc=description: self._set_default_sink(
                            name, desc
                        ),
                    )
                )
        except PactlError:
            item = Gtk.MenuItem(label="Salida de audio no disponible")
            item.set_sensitive(False)
            items.append(item)

        items.append(make_settings_item("sound"))
        return items
