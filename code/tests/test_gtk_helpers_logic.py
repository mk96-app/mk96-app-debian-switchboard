from mk96_app_debian_switchboard.gtk_helpers import device_action_labels


def test_device_action_labels_connected():
    assert device_action_labels(True) == ("Desconectar", "Reconectar")


def test_device_action_labels_disconnected():
    assert device_action_labels(False) == ("Conectar", "Reconectar")
