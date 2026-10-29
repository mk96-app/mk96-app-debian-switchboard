"""Construye el icono de bandeja (AyatanaAppIndicator3) y el menú combinado de módulos."""

import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, GLib, Gtk

from mk96_app_debian_switchboard.menu_groups import format_group_label, group_modules

APP_ID = "mk96-app-debian-switchboard"
ICON_NAME = "mk96-app-debian-switchboard-symbolic"
# AppIndicator resuelve ICON_NAME buscando <ICONS_DIR>/hicolor/scalable/apps/<ICON_NAME>.svg,
# como un icon theme más (no requiere instalar el icono en el sistema).
ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")
REFRESH_INTERVAL_MS = 5000


class Tray:
    def __init__(self, modules):
        self._modules = [m for m in modules if m.is_available()]
        self._refresh_source_id = None

        # El menú es un único Gtk.Menu persistente (no se recrea en cada rebuild):
        # así el refresco periódico solo actualiza su contenido sin afectar a si
        # está abierto o cerrado, y las señales show/hide siguen conectadas siempre
        # al mismo objeto.
        self._menu = Gtk.Menu()
        self._menu.connect("show", self._on_menu_show)
        self._menu.connect("hide", self._on_menu_hide)

        self._indicator = AyatanaAppIndicator3.Indicator.new(
            APP_ID,
            ICON_NAME,
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self._indicator.set_icon_theme_path(ICONS_DIR)
        self._indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self._indicator.set_menu(self._menu)

        self.rebuild_menu()
        for module in self._modules:
            module.start()

    def _on_menu_show(self, _widget) -> None:
        # No reconstruir el menú de forma síncrona aquí: esta señal se emite en mitad
        # del propio proceso de apertura de GTK (gtk_widget_show), y mutar los hijos del
        # menú en ese momento reentante deja el enrutado de clics de GtkMenuShell
        # apuntando a widgets obsoletos (el menú se ve bien pero nada responde a click).
        # Se difiere al siguiente ciclo del mainloop, ya con la apertura terminada.
        GLib.idle_add(self._refresh_after_show)
        if self._refresh_source_id is None:
            self._refresh_source_id = GLib.timeout_add(
                REFRESH_INTERVAL_MS, self._on_refresh_tick
            )

    def _refresh_after_show(self) -> bool:
        self.rebuild_menu()
        return GLib.SOURCE_REMOVE

    def _on_menu_hide(self, _widget) -> None:
        if self._refresh_source_id is not None:
            GLib.source_remove(self._refresh_source_id)
            self._refresh_source_id = None

    def _on_refresh_tick(self) -> bool:
        self.rebuild_menu()
        return GLib.SOURCE_CONTINUE

    def rebuild_menu(self) -> None:
        for child in self._menu.get_children():
            self._menu.remove(child)

        # Un submenú por grupo temático; el estado actual va en la etiqueta para poder
        # leerlo sin abrir el submenú.
        for group, modules in group_modules(self._modules):
            group_item = Gtk.MenuItem(label=format_group_label(group, [m.summary() for m in modules]))
            submenu = Gtk.Menu()
            for index, module in enumerate(modules):
                if len(modules) > 1:
                    if index > 0:
                        submenu.append(Gtk.SeparatorMenuItem())
                    header = Gtk.MenuItem(label=module.name)
                    header.set_sensitive(False)
                    submenu.append(header)
                for item in module.build_menu_section():
                    submenu.append(item)
            group_item.set_submenu(submenu)
            self._menu.append(group_item)

        self._menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Salir")
        quit_item.connect("activate", lambda _w: Gtk.main_quit())
        self._menu.append(quit_item)

        self._menu.show_all()

    def shutdown(self) -> None:
        if self._refresh_source_id is not None:
            GLib.source_remove(self._refresh_source_id)
            self._refresh_source_id = None
        for module in self._modules:
            module.stop()
