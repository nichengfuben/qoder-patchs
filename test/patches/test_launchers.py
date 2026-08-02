from __future__ import annotations

from pathlib import Path

from patches.cursor.cursor_launchers import (
    _AG_CMD,
    _CURSOR_AGENT_CMD_TAIL,
    sc_statusline_cmd,
    sc_statusline_sh,
)


def test_agent_cmd_does_not_use_endlocal_ps_hack() -> None:
    """endlocal & \"%_PS%\" -NoProfile 在 %_PS% 空展开时会拆成 ofile 等假命令。"""
    for body in (_AG_CMD, _CURSOR_AGENT_CMD_TAIL):
        assert "endlocal &" not in body
        assert '"%_PS%"' not in body
        assert "-NoProfile" in body
        assert "powershell.exe" in body


def test_statusline_launcher_py38_pip_fallback() -> None:
    """源码直跑可用 -S 提速；pip 安装的 -m 分支不能 -S（会跳过 site-packages）。"""
    cmd = sc_statusline_cmd(Path("/opt/patcher/src"))
    assert "-S -X utf8 \"%PYTHONPATH%\\sc\\statusline_fast.py\"" in cmd
    assert '"%PY%" -X utf8 -m sc.statusline_fast' in cmd
    assert "-S -X utf8 -m sc.statusline_fast" not in cmd

    sh = sc_statusline_sh(Path("/opt/patcher/src"))
    assert '-S -X utf8 "$PYTHONPATH/sc/statusline_fast.py"' in sh
    assert 'exec "$PY" -X utf8 -m sc.statusline_fast' in sh
    assert "-S -X utf8 -m sc.statusline_fast" not in sh
