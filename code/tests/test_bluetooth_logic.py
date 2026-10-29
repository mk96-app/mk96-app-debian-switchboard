from mk96_app_debian_switchboard.modules.bluetooth import extract_paired_devices, format_device_label


def test_format_device_label_connected():
    assert format_device_label("Auriculares BT", True) == "● Auriculares BT"


def test_format_device_label_disconnected():
    assert format_device_label("Teclado BT", False) == "   Teclado BT"


def test_extract_paired_devices_filters_unpaired():
    managed_objects = {
        "/org/bluez/hci0/dev_AA": {
            "org.bluez.Device1": {"Paired": True, "Connected": True, "Name": "Auriculares"}
        },
        "/org/bluez/hci0/dev_BB": {
            "org.bluez.Device1": {"Paired": False, "Connected": False, "Name": "Desconocido"}
        },
    }
    devices = extract_paired_devices(managed_objects)
    assert devices == [("/org/bluez/hci0/dev_AA", "Auriculares", True)]


def test_extract_paired_devices_ignores_non_device_interfaces():
    managed_objects = {
        "/org/bluez/hci0": {"org.bluez.Adapter1": {"Powered": True}},
    }
    assert extract_paired_devices(managed_objects) == []


def test_extract_paired_devices_falls_back_to_address_when_no_name():
    managed_objects = {
        "/org/bluez/hci0/dev_CC": {
            "org.bluez.Device1": {"Paired": True, "Connected": False, "Address": "AA:BB:CC:DD:EE:FF"}
        },
    }
    devices = extract_paired_devices(managed_objects)
    assert devices == [("/org/bluez/hci0/dev_CC", "AA:BB:CC:DD:EE:FF", False)]


def test_format_bluetooth_summary():
    from mk96_app_debian_switchboard.modules.bluetooth import format_bluetooth_summary

    assert format_bluetooth_summary(2) == "2 Bluetooth"
    assert format_bluetooth_summary(0) is None


def test_find_adapter_path():
    from mk96_app_debian_switchboard.modules.bluetooth import find_adapter_path

    managed = {
        "/org/bluez": {},
        "/org/bluez/hci0": {"org.bluez.Adapter1": {"Powered": True}},
        "/org/bluez/hci0/dev_AA": {"org.bluez.Device1": {}},
    }
    assert find_adapter_path(managed) == "/org/bluez/hci0"
    assert find_adapter_path({"/org/bluez": {}}) is None
