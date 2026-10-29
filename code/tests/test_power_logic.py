from mk96_app_debian_switchboard.modules.power import format_battery_label, format_profile_label


def test_format_profile_label_active():
    assert format_profile_label("performance", True) == "● Rendimiento"


def test_format_profile_label_inactive():
    assert format_profile_label("power-saver", False) == "   Ahorro de energía"


def test_format_profile_label_unknown_id_falls_back_to_raw_id():
    assert format_profile_label("custom-profile", False) == "   custom-profile"


def test_format_battery_label_discharging():
    assert format_battery_label(87.4, 2) == "Batería: 87% (en uso)"


def test_format_battery_label_unknown_state():
    assert format_battery_label(50.0, 99) == "Batería: 50% (desconocido)"


def test_format_power_summary_profile_and_battery():
    from mk96_app_debian_switchboard.modules.power import format_power_summary

    assert format_power_summary("balanced", 85.4) == "Equilibrado · 85%"


def test_format_power_summary_without_battery():
    from mk96_app_debian_switchboard.modules.power import format_power_summary

    assert format_power_summary("performance", None) == "Rendimiento"


def test_format_power_summary_without_profile():
    from mk96_app_debian_switchboard.modules.power import format_power_summary

    assert format_power_summary(None, 50.0) == "50%"
    assert format_power_summary(None, None) is None
