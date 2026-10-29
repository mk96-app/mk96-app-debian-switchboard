from mk96_app_debian_switchboard.pa_events import affects_menu, affects_panel, parse_event


def test_parse_event():
    assert parse_event("Event 'change' on sink #4") == ("change", "sink", 4)
    assert parse_event("Event 'new' on sink-input #193\n") == ("new", "sink-input", 193)
    assert parse_event("Event 'remove' on source-output #5") == ("remove", "source-output", 5)


def test_parse_event_server_has_no_index():
    assert parse_event("Event 'change' on server") == ("change", "server", None)


def test_parse_event_ignores_garbage():
    assert parse_event("") is None
    assert parse_event("algo raro") is None


def test_affects_menu_only_for_outputs_defaults_and_cards():
    assert affects_menu(("change", "sink", 1))
    assert affects_menu(("new", "sink", 9))
    assert affects_menu(("change", "server", None))
    assert affects_menu(("change", "card", 2))
    assert not affects_menu(("change", "sink-input", 3))
    assert not affects_menu(("new", "source-output", 3))


def test_affects_panel_for_streams_outputs_and_defaults():
    assert affects_panel(("new", "sink-input", 3))
    assert affects_panel(("remove", "sink-input", 3))
    assert affects_panel(("change", "sink", 1))
    assert affects_panel(("change", "source", 5))
    assert affects_panel(("change", "server", None))
    assert not affects_panel(("change", "card", 2))
    assert not affects_panel(("change", "source-output", 3))
