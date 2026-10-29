import json

from mk96_app_debian_switchboard.modules.audio import (
    format_device_label,
    is_sink_usable,
    parse_mute_status,
    parse_sinks,
    parse_volume_percent,
    resolve_description,
)


def test_format_device_label_marks_default():
    assert format_device_label("Altavoces", True) == "● Altavoces"


def test_format_device_label_marks_non_default():
    assert format_device_label("Auriculares", False) == "   Auriculares"


def test_parse_volume_percent():
    assert parse_volume_percent("100%") == 100


def test_parse_volume_percent_other_value():
    assert parse_volume_percent("47%") == 47


def test_parse_sinks_extracts_name_and_description():
    output = (
        '[{"name": "alsa_output.pci-sink", "description": "Altavoces internos", '
        '"other_field": "ignored"}]'
    )
    assert parse_sinks(output) == [("alsa_output.pci-sink", "Altavoces internos")]


def test_parse_sinks_empty_list():
    assert parse_sinks("[]") == []


def test_is_sink_usable_true_when_no_ports():
    assert is_sink_usable({"name": "sink1"}) is True


def test_is_sink_usable_true_when_active_port_available():
    sink = {
        "active_port": "out",
        "ports": [{"name": "out", "availability": "available"}],
    }
    assert is_sink_usable(sink) is True


def test_is_sink_usable_true_when_availability_unknown():
    sink = {
        "active_port": "out",
        "ports": [{"name": "out", "availability": "availability unknown"}],
    }
    assert is_sink_usable(sink) is True


def test_is_sink_usable_false_when_active_port_not_available():
    sink = {
        "active_port": "[Out] HDMI2",
        "ports": [{"name": "[Out] HDMI2", "availability": "not available"}],
    }
    assert is_sink_usable(sink) is False


def test_resolve_description_returns_normal_description():
    sink = {"description": "sof-hda-dsp Speaker + Headphones"}
    assert resolve_description(sink) == "sof-hda-dsp Speaker + Headphones"


def test_resolve_description_falls_back_when_null_with_product_and_port():
    sink = {
        "description": "(null)",
        "properties": {"device.product.name": "Arctis Nova Pro Wireless"},
        "active_port": "iec958-stereo-output",
        "ports": [
            {"name": "iec958-stereo-output", "description": "Digital Output (S/PDIF)"}
        ],
    }
    assert (
        resolve_description(sink)
        == "Arctis Nova Pro Wireless (Digital Output (S/PDIF))"
    )


def test_resolve_description_falls_back_to_card_name_when_no_product_name():
    sink = {
        "description": "(null)",
        "properties": {"alsa.card_name": "Arctis Nova Pro Wireless"},
    }
    assert resolve_description(sink) == "Arctis Nova Pro Wireless"


def test_resolve_description_falls_back_to_sink_name_as_last_resort():
    sink = {"description": "(null)", "name": "alsa_output.usb-weird-device", "properties": {}}
    assert resolve_description(sink) == "alsa_output.usb-weird-device"


def test_parse_mute_status_yes():
    assert parse_mute_status("Mute: yes") is True


def test_parse_mute_status_no():
    assert parse_mute_status("Mute: no\n") is False


def test_parse_sinks_filters_unavailable_and_resolves_null_description():
    output = json.dumps(
        [
            {
                "name": "hdmi2",
                "description": "HDMI2",
                "active_port": "p2",
                "ports": [{"name": "p2", "availability": "not available"}],
            },
            {
                "name": "usb_headset",
                "description": "(null)",
                "properties": {"device.product.name": "Arctis Nova Pro Wireless"},
                "active_port": "p_usb",
                "ports": [{"name": "p_usb", "description": "Digital Output (S/PDIF)"}],
            },
        ]
    )
    assert parse_sinks(output) == [
        ("usb_headset", "Arctis Nova Pro Wireless (Digital Output (S/PDIF))")
    ]


def test_format_audio_summary_shows_volume():
    from mk96_app_debian_switchboard.modules.audio import format_audio_summary

    assert format_audio_summary(65, False) == "65%"


def test_format_audio_summary_muted_wins_over_volume():
    from mk96_app_debian_switchboard.modules.audio import format_audio_summary

    assert format_audio_summary(65, True) == "Silenciado"
