from mk96_app_debian_switchboard.modules.network import (
    decode_ssid,
    extract_wifi_ssid,
    filter_available_saved_connections,
    format_activation_error,
    format_connection_label,
    is_activation_failure,
    is_wifi_connection,
)


def test_format_connection_label_active():
    assert format_connection_label("CasaWifi", True) == "● CasaWifi"


def test_format_connection_label_inactive():
    assert format_connection_label("Oficina", False) == "   Oficina"


def test_is_wifi_connection_true():
    settings = {"connection": {"type": "802-11-wireless", "id": "CasaWifi"}}
    assert is_wifi_connection(settings) is True


def test_is_wifi_connection_false_for_ethernet():
    settings = {"connection": {"type": "802-3-ethernet", "id": "Cableada"}}
    assert is_wifi_connection(settings) is False


def test_is_wifi_connection_false_for_missing_connection_block():
    assert is_wifi_connection({}) is False


def test_decode_ssid_from_byte_list():
    assert decode_ssid([67, 97, 115, 97, 87, 105, 102, 105]) == "CasaWifi"


def test_extract_wifi_ssid_present():
    settings = {"802-11-wireless": {"ssid": [67, 97, 115, 97]}}
    assert extract_wifi_ssid(settings) == "Casa"


def test_extract_wifi_ssid_missing_returns_none():
    assert extract_wifi_ssid({}) is None


def test_filter_available_saved_connections_keeps_only_in_range():
    saved = [
        ("/conn/1", "CasaWifi", "CasaWifi"),
        ("/conn/2", "OficinaWifi", "OficinaWifi"),
    ]
    available = {"CasaWifi"}
    assert filter_available_saved_connections(saved, available) == [
        ("/conn/1", "CasaWifi")
    ]


def test_filter_available_saved_connections_empty_when_none_in_range():
    saved = [("/conn/1", "CasaWifi", "CasaWifi")]
    assert filter_available_saved_connections(saved, set()) == []


def test_is_activation_failure_true_for_wrong_password():
    assert is_activation_failure(state=4, reason=9) is True


def test_is_activation_failure_false_for_activated():
    assert is_activation_failure(state=2, reason=1) is False


def test_is_activation_failure_false_for_user_disconnected():
    assert is_activation_failure(state=4, reason=2) is False


def test_is_activation_failure_false_for_normal_deactivation_no_reason():
    assert is_activation_failure(state=4, reason=1) is False


def test_format_activation_error_known_reason():
    assert (
        format_activation_error("CasaWifi", 9)
        == "No se pudo conectar a CasaWifi: faltan credenciales (contraseña incorrecta o no guardada)"
    )


def test_format_activation_error_unknown_reason():
    assert (
        format_activation_error("CasaWifi", 999)
        == "No se pudo conectar a CasaWifi: motivo desconocido (999)"
    )


def test_format_network_summary_only_active_wifi():
    from mk96_app_debian_switchboard.modules.network import format_network_summary

    active = {"Casa", "Conexión cableada 1", "docker0", "br-33ea"}
    assert format_network_summary(active, {"Casa", "Oficina"}) == "Casa"


def test_format_network_summary_no_active_wifi():
    from mk96_app_debian_switchboard.modules.network import format_network_summary

    assert format_network_summary({"docker0"}, {"Casa"}) is None
    assert format_network_summary(set(), {"Casa"}) is None


def test_find_wifi_device_path():
    from mk96_app_debian_switchboard.modules.network import find_wifi_device_path

    assert find_wifi_device_path([("/d/1", 1), ("/d/2", 2), ("/d/3", 2)]) == "/d/2"
    assert find_wifi_device_path([("/d/1", 1)]) is None
