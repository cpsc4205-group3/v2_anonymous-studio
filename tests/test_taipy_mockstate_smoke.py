from __future__ import annotations

import pytest


def test_taipy_mockstate_smoke():
    try:
        from taipy.gui import Gui
        from taipy.gui.test import MockState
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"Taipy MockState unavailable in this environment: {exc}")

    state = MockState(Gui(""), counter=1, label="demo")
    assert state.counter == 1
    assert state.label == "demo"

    state.counter = 2
    assert state.counter == 2
