from mk96_app_debian_switchboard.dbus_utils import ServiceUnavailable
from mk96_app_debian_switchboard.radio_cycle import cycle_radio


class FakeScheduler:
    """Guarda los callbacks para ejecutarlos a mano, en orden, sin temporizadores reales."""

    def __init__(self):
        self.pending = []

    def __call__(self, delay_ms, callback):
        self.pending.append((delay_ms, callback))

    def run_next(self):
        _delay, callback = self.pending.pop(0)
        callback()


def test_cycle_radio_turns_off_then_on_then_ready():
    calls = []
    scheduler = FakeScheduler()

    cycle_radio(
        set_enabled=calls.append,
        on_ready=lambda: calls.append("ready"),
        on_error=lambda exc: calls.append(("error", exc)),
        schedule=scheduler,
        off_ms=1500,
        ready_ms=3000,
    )
    assert calls == [False]
    assert scheduler.pending[0][0] == 1500

    scheduler.run_next()
    assert calls == [False, True]
    assert scheduler.pending[0][0] == 3000

    scheduler.run_next()
    assert calls == [False, True, "ready"]


def test_cycle_radio_error_turning_off_aborts():
    errors = []
    scheduler = FakeScheduler()

    def set_enabled(value):
        raise ServiceUnavailable("sin permiso")

    cycle_radio(set_enabled, lambda: errors.append("ready"), errors.append, scheduler)
    assert [type(e) for e in errors] == [ServiceUnavailable]
    assert scheduler.pending == []


def test_cycle_radio_error_turning_on_skips_ready():
    results = []
    scheduler = FakeScheduler()

    def set_enabled(value):
        if value:
            raise ServiceUnavailable("fallo al encender")

    cycle_radio(set_enabled, lambda: results.append("ready"), results.append, scheduler)
    scheduler.run_next()
    assert [type(e) for e in results] == [ServiceUnavailable]
    assert scheduler.pending == []
