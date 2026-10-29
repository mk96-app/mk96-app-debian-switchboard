"""Contrato común que implementa cada módulo del tray (audio, energía, red, bluetooth, ...).

Nota de arquitectura: AyatanaAppIndicator3 solo funciona con GTK3 (no existe versión GTK4/
libadwaita de la librería, y GTK3/GTK4 no pueden coexistir en el mismo proceso), así que toda
la app -incluidos los widgets que construyen los módulos- usa GTK3 (Gtk.Menu/Gtk.MenuItem).
"""

from abc import ABC, abstractmethod


class Module(ABC):
    name: str
    group: str  # submenú del tray en el que se agrupa (ver menu_groups.py)
    icon: str

    def __init__(self, on_changed):
        """on_changed: callback sin argumentos que el módulo invoca cuando su
        estado cambia y el menú del tray debe reconstruirse."""
        self._on_changed = on_changed

    @abstractmethod
    def is_available(self) -> bool:
        """False si el servicio D-Bus que respalda este módulo no existe en este sistema."""

    @abstractmethod
    def build_menu_section(self) -> list:
        """Devuelve una lista de Gtk.MenuItem para insertar en el menú del tray."""

    def summary(self) -> str | None:
        """Texto corto con el estado actual para la etiqueta del grupo, o None."""
        return None

    def start(self) -> None:
        """Suscribirse a señales D-Bus relevantes. No-op por defecto."""

    def stop(self) -> None:
        """Desuscribirse de señales D-Bus. No-op por defecto."""

    def notify_changed(self) -> None:
        self._on_changed()
