from mk96_app_debian_switchboard.modules.display import has_schema


def test_has_schema_true_for_existing_schema():
    assert has_schema("org.gnome.settings-daemon.plugins.color") is True


def test_has_schema_false_for_nonexistent_schema():
    assert has_schema("org.mk96appdebianswitchboard.this-schema-does-not-exist") is False


def test_format_display_summary():
    from mk96_app_debian_switchboard.modules.display import format_display_summary

    assert format_display_summary(True) == "Luz nocturna"
    assert format_display_summary(False) is None
