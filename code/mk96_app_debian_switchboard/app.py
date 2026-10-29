"""Punto de entrada: registra los módulos v1 y arranca el mainloop de GTK3."""

import importlib.resources
import signal

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from mk96_app_debian_switchboard.modules.audio import AudioModule
from mk96_app_debian_switchboard.modules.bluetooth import BluetoothModule
from mk96_app_debian_switchboard.modules.display import DisplayModule
from mk96_app_debian_switchboard.modules.focus import FocusModule
from mk96_app_debian_switchboard.modules.network import NetworkModule
from mk96_app_debian_switchboard.modules.power import PowerModule
from mk96_app_debian_switchboard.tray import Tray

MODULE_CLASSES = [
    AudioModule,
    DisplayModule,
    FocusModule,
    PowerModule,
    NetworkModule,
    BluetoothModule,
]


def _print_banner() -> None:
    try:
        banner = importlib.resources.files("mk96_app_debian_switchboard").joinpath("banner.txt").read_text()
        print(banner)
    except Exception:
        pass


def main() -> None:
    _print_banner()

    tray_ref = {}

    def on_changed():
        tray = tray_ref.get("tray")
        if tray is not None:
            tray.rebuild_menu()

    modules = [cls(on_changed) for cls in MODULE_CLASSES]
    tray = Tray(modules)
    tray_ref["tray"] = tray

    # Sin esto, SIGTERM/SIGINT matan el proceso sin pasar por el finally y los procesos hijo
    # (pactl subscribe) quedan huérfanos.
    for sig in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, Gtk.main_quit)

    try:
        Gtk.main()
    finally:
        tray.shutdown()


if __name__ == "__main__":
    main()
