"""Tests for interactive patch selection menu."""

from __future__ import annotations

from types import SimpleNamespace

from cli import menu
from echotools.media.console.uiwidgets.ui_select import SelectionResult


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

    def fake_run_select(ui, title, options, default_index=0):
        captured["title"] = title
        captured["options"] = list(options)
        return SelectionResult(1, options[1])

    monkeypatch.setattr(menu, "run_select", fake_run_select)
    assert menu.patch_select_menu(patches) == ["cursor-agent"]
    assert "全部补丁" in captured["options"]
    assert "取消" in captured["options"]


def test_patch_select_menu_all(monkeypatch) -> None:
    patches = {
        "a": SimpleNamespace(metadata=SimpleNamespace(display_name="A", version="1")),
        "b": SimpleNamespace(metadata=SimpleNamespace(display_name="B", version="1")),
    }

    def fake_run_select(ui, title, options, default_index=0):
        return SelectionResult(0, options[0])

    monkeypatch.setattr(menu, "run_select", fake_run_select)
    assert menu.patch_select_menu(patches) == ["a", "b"]


def test_patch_select_menu_cancel(monkeypatch) -> None:
    patches = {
        "a": SimpleNamespace(metadata=SimpleNamespace(display_name="A", version="1")),
    }

    def fake_run_select(ui, title, options, default_index=0):
        return SelectionResult(len(options) - 1, options[-1])

    monkeypatch.setattr(menu, "run_select", fake_run_select)
    assert menu.patch_select_menu(patches) == []
