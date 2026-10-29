import json

from mk96_app_debian_switchboard.audio_panel import (
    format_app_label,
    mic_mute_icon_name,
    mute_icon_name,
    parse_get_volume_output,
    format_app_row_label,
    parse_sink_inputs,
    rows_signature,
)


def test_format_app_label_uses_application_name():
    assert format_app_label({"application.name": "Firefox", "media.name": "Netflix"}) == "Firefox"


def test_format_app_label_falls_back_to_media_name():
    assert format_app_label({"media.name": "Netflix"}) == "Netflix"


def test_format_app_label_falls_back_to_default():
    assert format_app_label({}) == "Aplicación desconocida"


def test_parse_get_volume_output():
    text = "Volume: front-left: 65536 / 100% / 0.00 dB,   front-right: 65536 / 100% / 0.00 dB"
    assert parse_get_volume_output(text) == 100


def test_parse_get_volume_output_other_value():
    text = "Volume: front-left: 39321 / 60% / -12.00 dB"
    assert parse_get_volume_output(text) == 60


def test_mute_icon_name():
    assert mute_icon_name(True) == "audio-volume-muted-symbolic"
    assert mute_icon_name(False) == "audio-volume-high-symbolic"


def test_mic_mute_icon_name():
    assert mic_mute_icon_name(True) == "microphone-disabled-symbolic"
    assert mic_mute_icon_name(False) == "microphone-sensitivity-high-symbolic"


def test_parse_sink_inputs():
    output = json.dumps(
        [
            {
                "index": 42,
                "mute": False,
                "volume": {"front-left": {"value_percent": "80%"}},
                "properties": {"application.name": "Firefox", "media.name": "Netflix"},
            }
        ]
    )
    assert parse_sink_inputs(output) == [
        {"index": 42, "label": "Firefox", "muted": False, "corked": False, "volume_percent": 80}
    ]


def test_parse_sink_inputs_empty():
    assert parse_sink_inputs("[]") == []


def test_parse_sink_inputs_reads_corked():
    output = json.dumps(
        [
            {
                "index": 7,
                "mute": False,
                "corked": True,
                "volume": {"front-left": {"value_percent": "50%"}},
                "properties": {"application.name": "spotify"},
            }
        ]
    )
    assert parse_sink_inputs(output)[0]["corked"] is True


def test_format_app_row_label_marks_paused_apps():
    assert format_app_row_label("Spotify", True) == "Spotify · en pausa"
    assert format_app_row_label("Spotify", False) == "Spotify"


def _app(index=1, label="Firefox", muted=False, corked=False, volume_percent=50):
    return {
        "index": index,
        "label": label,
        "muted": muted,
        "corked": corked,
        "volume_percent": volume_percent,
    }


def test_rows_signature_changes_with_title_mute_and_pause():
    base = rows_signature([_app()])
    assert rows_signature([_app(label="YouTube")]) != base
    assert rows_signature([_app(muted=True)]) != base
    assert rows_signature([_app(corked=True)]) != base
    assert rows_signature([_app(index=2)]) != base


def test_rows_signature_ignores_volume():
    # El volumen se actualiza en el slider sin reconstruir la fila (no cortar un arrastre).
    assert rows_signature([_app(volume_percent=10)]) == rows_signature([_app(volume_percent=90)])
