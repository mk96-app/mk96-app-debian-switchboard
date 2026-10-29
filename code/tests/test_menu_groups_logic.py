from mk96_app_debian_switchboard.menu_groups import format_group_label, group_modules


class FakeModule:
    def __init__(self, name, group):
        self.name = name
        self.group = group


def test_group_modules_preserves_first_appearance_order():
    audio = FakeModule("Salida de audio", "Audio")
    display = FakeModule("Pantalla", "Pantalla")
    focus = FakeModule("No molestar", "Pantalla")
    power = FakeModule("Energía", "Energía")

    result = group_modules([audio, display, focus, power])

    assert result == [
        ("Audio", [audio]),
        ("Pantalla", [display, focus]),
        ("Energía", [power]),
    ]


def test_group_modules_empty():
    assert group_modules([]) == []


def test_group_modules_merges_non_adjacent_modules_of_same_group():
    a = FakeModule("A", "G1")
    b = FakeModule("B", "G2")
    c = FakeModule("C", "G1")

    assert group_modules([a, b, c]) == [("G1", [a, c]), ("G2", [b])]


def test_format_group_label_with_summary():
    assert format_group_label("Audio", ["65%"]) == "🔊 Audio · 65%"


def test_format_group_label_joins_non_empty_summaries():
    assert format_group_label("Pantalla", ["Luz nocturna", None, "No molestar"]) == (
        "🖥 Pantalla · Luz nocturna, No molestar"
    )


def test_format_group_label_without_summary():
    assert format_group_label("Energía", [None, ""]) == "⚡ Energía"


def test_format_group_label_unknown_group_has_no_icon():
    assert format_group_label("Otro", ["x"]) == "Otro · x"
