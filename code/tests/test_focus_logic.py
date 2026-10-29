from mk96_app_debian_switchboard.modules.focus import is_dnd_enabled


def test_is_dnd_enabled_when_banners_off():
    assert is_dnd_enabled(show_banners=False) is True


def test_is_dnd_enabled_false_when_banners_on():
    assert is_dnd_enabled(show_banners=True) is False


def test_format_focus_summary():
    from mk96_app_debian_switchboard.modules.focus import format_focus_summary

    assert format_focus_summary(True) == "No molestar"
    assert format_focus_summary(False) is None
