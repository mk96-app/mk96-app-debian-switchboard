"""Apagar y volver a encender una radio (Wi-Fi o Bluetooth) sin bloquear la interfaz.

Se usa para "Reconectar": primero se apaga la radio, se espera a que el sistema la dé por
apagada, se enciende y, pasado un margen para que vuelva a escanear/anunciar, se avisa con
`on_ready` para que quien llama (re)conecte el dispositivo o la red elegidos.
"""

from gi.repository import GLib

from mk96_app_debian_switchboard.dbus_utils import ServiceUnavailable

OFF_MS = 1500
READY_MS = 3000


def _glib_schedule(delay_ms, callback) -> None:
    GLib.timeout_add(delay_ms, lambda: (callback(), GLib.SOURCE_REMOVE)[1])


def cycle_radio(set_enabled, on_ready, on_error, schedule=_glib_schedule, off_ms=OFF_MS, ready_ms=READY_MS):
    """set_enabled(bool) enciende/apaga la radio y lanza ServiceUnavailable si falla.
    on_error(exc) se llama con ese error; si falla al encender, la radio queda apagada.
    `schedule` es inyectable para poder probar la secuencia sin temporizadores reales."""
    try:
        set_enabled(False)
    except ServiceUnavailable as exc:
        on_error(exc)
        return

    def turn_on() -> None:
        try:
            set_enabled(True)
        except ServiceUnavailable as exc:
            on_error(exc)
            return
        schedule(ready_ms, on_ready)

    schedule(off_ms, turn_on)
