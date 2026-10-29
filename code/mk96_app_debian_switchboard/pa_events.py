"""Suscripción a eventos de PulseAudio/PipeWire (`pactl subscribe`).

En vez de consultar por temporizador, el menú y el panel de audio se refrescan en cuanto
cambia una salida, un stream o el dispositivo por defecto (p. ej. unos cascos que se
conectan solos). Los eventos se agrupan con un pequeño debounce porque una sola acción
(conectar unos cascos, mover un slider) dispara varios seguidos.
"""

import re

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

DEBOUNCE_MS = 150
RESTART_DELAY_MS = 2000

_EVENT_RE = re.compile(r"^Event '(\w+)' on ([\w-]+)(?: #(\d+))?$")

# Qué tipos de objeto afectan a cada superficie de UI.
_MENU_KINDS = {"sink", "server", "card"}
_PANEL_KINDS = {"sink", "sink-input", "source", "server"}


def parse_event(line: str):
    """Lógica pura: "Event 'change' on sink #4" -> ("change", "sink", 4).
    Para "Event 'change' on server" el índice es None. Devuelve None si no es un evento."""
    match = _EVENT_RE.match(line.strip())
    if match is None:
        return None
    action, kind, index = match.groups()
    return action, kind, int(index) if index is not None else None


def affects_menu(event) -> bool:
    """Lógica pura: ¿cambia esto lo que muestra el menú (salidas, activa, volumen)?"""
    return event[1] in _MENU_KINDS


def affects_panel(event) -> bool:
    """Lógica pura: ¿cambia esto lo que muestra el panel de audio?"""
    return event[1] in _PANEL_KINDS


class PulseEvents:
    def __init__(self, on_menu_event, on_panel_event):
        self._on_menu_event = on_menu_event
        self._on_panel_event = on_panel_event
        self._process = None
        self._stopped = True
        self._menu_pending = False
        self._panel_pending = False
        self._flush_source_id = None
        self._restart_source_id = None

    def start(self) -> None:
        self._stopped = False
        self._spawn()

    def stop(self) -> None:
        self._stopped = True
        for attr in ("_flush_source_id", "_restart_source_id"):
            source_id = getattr(self, attr)
            if source_id is not None:
                GLib.source_remove(source_id)
                setattr(self, attr, None)
        if self._process is not None:
            self._process.force_exit()
            self._process = None

    def _spawn(self) -> None:
        launcher = Gio.SubprocessLauncher.new(
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
        )
        launcher.setenv("LC_ALL", "C", True)
        try:
            self._process = launcher.spawnv(["pactl", "subscribe"])
        except GLib.Error:
            self._schedule_restart()
            return
        stream = Gio.DataInputStream.new(self._process.get_stdout_pipe())
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line)

    def _on_line(self, stream, result) -> None:
        try:
            line, _length = stream.read_line_finish_utf8(result)
        except GLib.Error:
            line = None
        if line is None:  # EOF: pactl murió (p. ej. reinicio de PipeWire)
            self._process = None
            if not self._stopped:
                self._schedule_restart()
            return

        event = parse_event(line)
        if event is not None:
            self._menu_pending = self._menu_pending or affects_menu(event)
            self._panel_pending = self._panel_pending or affects_panel(event)
            if (self._menu_pending or self._panel_pending) and self._flush_source_id is None:
                self._flush_source_id = GLib.timeout_add(DEBOUNCE_MS, self._flush)
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line)

    def _flush(self) -> bool:
        self._flush_source_id = None
        menu, panel = self._menu_pending, self._panel_pending
        self._menu_pending = self._panel_pending = False
        if panel:
            self._on_panel_event()
        if menu:
            self._on_menu_event()
        return GLib.SOURCE_REMOVE

    def _schedule_restart(self) -> None:
        if self._restart_source_id is None:
            self._restart_source_id = GLib.timeout_add(RESTART_DELAY_MS, self._restart)

    def _restart(self) -> bool:
        self._restart_source_id = None
        if not self._stopped:
            self._spawn()
        return GLib.SOURCE_REMOVE
