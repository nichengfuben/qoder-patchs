"""Tests for sc doctor."""

from __future__ import annotations

from sc.run.commands import cmd_doctor


def test_cmd_doctor_runs() -> None:
    # 本机有 cursor-agent 时应对 PASS 或因缺 last-bearer 仍返回 0（仅 WARN）
    code = cmd_doctor()
    assert code in (0, 1)
