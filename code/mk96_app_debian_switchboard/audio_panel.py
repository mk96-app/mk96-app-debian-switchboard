"""Ventana propia (Gtk.Window normal, no menú de AppIndicator) con sliders reales de
volumen/mute para la salida y el micrófono por defecto, y un mixer con un slider por
cada aplicación que está reproduciendo sonido.

Los sliders solo pueden existir aquí: dentro del menú de AppIndicator, GNOME Shell solo
sabe dibujar texto/checkboxes (ver nota en gtk_helpers.py) -esta ventana la dibuja
directamente nuestro propio proceso, así que no tiene esa limitación.
"""

import json

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from mk96_app_debian_switchboard.modules.audio import PactlError, parse_volume_percent, run_pactl


def format_app_label(properties: dict) -> str:
    """Lógica pura: nombre a mostrar para un sink-input (stream de una app)."""
    return (
        properties.get("application.name")
        or properties.get("media.name")
        or "Aplicación desconocida"
    )


def parse_get_volume_output(pactl_output: str) -> int:
    """Lógica pura: 'Volume: front-left: 65536 / 100% / 0.00 dB, ...' -> 100
    (salida de texto de `pactl get-sink-volume`/`get-source-volume`)."""
    first_line = pactl_output.splitlines()[0]
    percent_field = first_line.split("/")[1].strip()
    return parse_volume_percent(percent_field)


def parse_sink_inputs(pactl_json_output: str) -> list:
    """Lógica pura: extrae de `pactl -f json list sink-inputs` los datos que necesita
    el mixer -> lista de dicts {index, label, muted, volume_percent}."""
    entries = json.loads(pactl_json_output)
    result = []
    for entry in entries:
        result.append(
            {
                "index": entry["index"],
                "label": format_app_label(entry.get("properties", {})),
                "muted": entry.get("mute", False),
                "corked": entry.get("corked", False),
                "volume_percent": parse_volume_percent(
                    entry["volume"]["front-left"]["value_percent"]
                ),
            }
        )
    return result


def format_app_row_label(label: str, corked: bool) -> str:
    """Lógica pura: nombre de la fila; un stream pausado (corked) se marca como tal."""
    return f"{label} · en pausa" if corked else label


def rows_signature(apps: list) -> tuple:
    """Lógica pura: lo que, si cambia, obliga a reconstruir las filas del mixer. El volumen
    queda fuera a propósito: se actualiza en el slider sin reconstruir (no cortar un drag)."""
    return tuple((a["index"], a["label"], a["muted"], a["corked"]) for a in apps)


def mute_icon_name(muted: bool) -> str:
    return "audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic"


def mic_mute_icon_name(muted: bool) -> str:
    return "microphone-disabled-symbolic" if muted else "microphone-sensitivity-high-symbolic"


class AudioPanel:
    """Ventana singleton: se crea una vez y se reutiliza (present()) en cada apertura."""

    def __init__(self):
        self._window = None
        self._app_rows_box = None
        self._output_scale = None
        self._output_mute_button = None
        self._mic_mute_button = None
        self._rows_signature = None
        self._app_scales = {}  # índice de sink-input -> Gtk.Scale
        self._updating = False  # True mientras se vuelca el estado real a los sliders

    def show(self) -> None:
        if self._window is None:
            self._build_window()
        self.refresh()
        self._window.present()

    def refresh(self) -> None:
        """Vuelca el estado actual de PulseAudio al panel (lo llama AudioModule al llegar
        un evento de `pactl subscribe`). No hace nada si el panel está cerrado."""
        if self._window is None:
            return
        self._refresh_master_row()
        self._rebuild_app_rows()

    def _on_close(self, _widget, _event) -> bool:
        # No basta con hide(): el ítem de menú que reabre el panel se activa vía AppIndicator
        # (dbusmenu), cuya señal 'activate' no lleva un timestamp real de evento X11/Wayland.
        # present() sobre una ventana ya retirada (hide()) puede ser bloqueado en silencio por
        # el "focus-stealing prevention" del gestor de ventanas (Mutter) al no tener un timestamp
        # de usuario válido -de ahí que solo la primera apertura (mapeo inicial) funcionara-.
        # Se destruye y se reconstruye entera en la siguiente show(), igual que la primera vez.
        self._window.destroy()
        self._window = None
        self._app_rows_box = None
        self._output_scale = None
        self._output_mute_button = None
        self._mic_mute_button = None
        self._rows_signature = None  # fuerza repoblar filas en la próxima apertura
        self._app_scales = {}
        return True

    def _build_window(self) -> None:
        window = Gtk.Window(title="Panel de audio")
        window.set_default_size(340, 320)
        window.set_border_width(12)
        window.connect("delete-event", self._on_close)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        window.add(content)

        content.add(self._build_master_row())
        content.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        apps_label = Gtk.Label(label="Aplicaciones")
        apps_label.set_xalign(0.0)
        content.add(apps_label)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        self._app_rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scroller.add(self._app_rows_box)
        content.add(scroller)

        # show_all() es imprescindible aquí: present() solo mapea la ventana en pantalla,
        # pero cada widget individual necesita su propio flag de visibilidad -sin esto la
        # ventana se abre pero se ve vacía (justo el bug reportado).
        window.show_all()

        self._window = window

    def _build_master_row(self) -> Gtk.Widget:
        grid = Gtk.Grid(column_spacing=8, row_spacing=6)

        self._output_mute_button = Gtk.Button()
        self._output_mute_button.set_relief(Gtk.ReliefStyle.NONE)
        self._output_mute_button.connect("clicked", lambda _b: self._toggle_output_mute())
        grid.attach(self._output_mute_button, 0, 0, 1, 1)

        output_label = Gtk.Label(label="Salida")
        output_label.set_xalign(0.0)
        grid.attach(output_label, 1, 0, 1, 1)

        self._output_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self._output_scale.set_hexpand(True)
        self._output_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self._output_scale.connect("value-changed", self._on_output_scale_changed)
        grid.attach(self._output_scale, 0, 1, 2, 1)

        self._mic_mute_button = Gtk.Button()
        self._mic_mute_button.set_relief(Gtk.ReliefStyle.NONE)
        self._mic_mute_button.connect("clicked", lambda _b: self._toggle_mic_mute())
        grid.attach(self._mic_mute_button, 0, 2, 1, 1)

        mic_label = Gtk.Label(label="Micrófono")
        mic_label.set_xalign(0.0)
        grid.attach(mic_label, 1, 2, 1, 1)

        return grid

    def _on_output_scale_changed(self, scale) -> None:
        if self._updating:
            return
        percent = int(scale.get_value())
        try:
            run_pactl("set-sink-volume", "@DEFAULT_SINK@", f"{percent}%")
        except PactlError:
            pass

    def _toggle_output_mute(self) -> None:
        try:
            run_pactl("set-sink-mute", "@DEFAULT_SINK@", "toggle")
        except PactlError:
            pass
        self._refresh_master_row()

    def _toggle_mic_mute(self) -> None:
        try:
            run_pactl("set-source-mute", "@DEFAULT_SOURCE@", "toggle")
        except PactlError:
            pass
        self._refresh_master_row()

    def _refresh_master_row(self) -> None:
        try:
            volume_percent = parse_get_volume_output(
                run_pactl("get-sink-volume", "@DEFAULT_SINK@")
            )
        except (PactlError, IndexError):
            volume_percent = None
        if volume_percent is not None and not self._output_scale.has_grab():
            self._set_scale_value(self._output_scale, volume_percent)

        try:
            output_muted = run_pactl("get-sink-mute", "@DEFAULT_SINK@").strip().endswith("yes")
            self._output_mute_button.set_image(
                Gtk.Image.new_from_icon_name(mute_icon_name(output_muted), Gtk.IconSize.BUTTON)
            )
        except PactlError:
            pass

        try:
            mic_muted = run_pactl("get-source-mute", "@DEFAULT_SOURCE@").strip().endswith("yes")
            self._mic_mute_button.set_image(
                Gtk.Image.new_from_icon_name(
                    mic_mute_icon_name(mic_muted), Gtk.IconSize.BUTTON
                )
            )
        except PactlError:
            pass

    def _rebuild_app_rows(self) -> None:
        try:
            apps = parse_sink_inputs(run_pactl("-f", "json", "list", "sink-inputs"))
        except PactlError:
            apps = []

        signature = rows_signature(apps)
        if signature != self._rows_signature:
            for child in self._app_rows_box.get_children():
                self._app_rows_box.remove(child)
            self._app_scales = {}
            for app in apps:
                self._app_rows_box.add(self._build_app_row(app))
            self._app_rows_box.show_all()
            self._rows_signature = signature

        # Mismas filas: solo se sincroniza el volumen (sin reconstruir, para no cortar un drag).
        for app in apps:
            scale = self._app_scales.get(app["index"])
            if scale is not None and not scale.has_grab():
                self._set_scale_value(scale, app["volume_percent"])

    def _set_scale_value(self, scale, percent: int) -> None:
        # set_value emite value-changed, que reescribiría el volumen en PulseAudio.
        self._updating = True
        try:
            scale.set_value(percent)
        finally:
            self._updating = False

    def _build_app_row(self, app: dict) -> Gtk.Widget:
        grid = Gtk.Grid(column_spacing=8, row_spacing=2)

        mute_button = Gtk.Button()
        mute_button.set_relief(Gtk.ReliefStyle.NONE)
        mute_button.set_image(
            Gtk.Image.new_from_icon_name(mute_icon_name(app["muted"]), Gtk.IconSize.BUTTON)
        )
        mute_button.connect(
            "clicked", lambda _b, index=app["index"]: self._toggle_app_mute(index)
        )
        grid.attach(mute_button, 0, 0, 1, 1)

        label = Gtk.Label(label=format_app_row_label(app["label"], app["corked"]))
        label.set_xalign(0.0)
        if app["corked"]:
            label.get_style_context().add_class("dim-label")
        grid.attach(label, 1, 0, 1, 1)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        scale.set_value(app["volume_percent"])
        scale.set_hexpand(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.connect(
            "value-changed", lambda s, index=app["index"]: self._on_app_scale_changed(s, index)
        )
        grid.attach(scale, 0, 1, 2, 1)
        self._app_scales[app["index"]] = scale

        return grid

    def _on_app_scale_changed(self, scale, index: int) -> None:
        if self._updating:
            return
        percent = int(scale.get_value())
        try:
            run_pactl("set-sink-input-volume", str(index), f"{percent}%")
        except PactlError:
            pass

    def _toggle_app_mute(self, index: int) -> None:
        try:
            run_pactl("set-sink-input-mute", str(index), "toggle")
        except PactlError:
            pass
        # Refresco inmediato del icono de mute, sin esperar al evento de pactl subscribe.
        self._rebuild_app_rows()
