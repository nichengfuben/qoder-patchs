"""Tests for interactive patch selection menu."""

from __future__ import annotations

from types import SimpleNamespace

from cli import menu


class _FakeAsk:
    def __init__(self, value):
        self._value = value

    def ask(self):
        return self._value


def test_patch_select_menu_enter_selects_one(monkeypatch) -> None:
    patches = {
        "cursor-agent": SimpleNamespace(
            metadata=SimpleNamespace(display_name="Cursor", version="1")
        ),
        "remove-qoder-warning": SimpleNamespace(
            metadata=SimpleNamespace(display_name="Qoder", version="1")
        ),
    }
    captured: dict = {}

    def fake_select(prompt, choices=None, style=None, instruction=None):
        captured["prompt"] = prompt
        captured["values"] = [c.value for c in choices]
        return _FakeAsk(["cursor-agent"])

    monkeypatch.setattr(menu.questionary, "select", fake_select)
    assert menu.patch_select_menu(patches) == ["cursor-agent"]
    assert ["cursor-agent", "remove-qoder-warning"] in captured["values"]
    assert [] in captured["values"]


def test_patch_select_menu_all(monkeypatch) -> None:
    patches = {
        "a": SimpleNamespace(metadata=SimpleNamespace(display_name="A", version="1")),
        "b": SimpleNamespace(metadata=SimpleNamespace(display_name="B", version="1")),
    }

    def fake_select(prompt, choices=None, style=None, instruction=None):
        return _FakeAsk(list(patches.keys()))

    monkeypatch.setattr(menu.questionary, "select", fake_select)
    assert menu.patch_select_menu(patches) == ["a", "b"]


def test_patch_select_menu_cancel(monkeypatch) -> None:
    patches = {
        "a": SimpleNamespace(metadata=SimpleNamespace(display_name="A", version="1")),
    }

    def fake_select(prompt, choices=None, style=None, instruction=None):
        return _FakeAsk([])

    monkeypatch.setattr(menu.questionary, "select", fake_select)
    assert menu.patch_select_menu(patches) == []
