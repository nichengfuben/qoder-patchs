from __future__ import annotations

"""Multi-instance auto loop: leader election + usage polling."""

import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from sc.core.paths import cursor_config_dir
from sc.core.encoding import utf8_env
from sc.run import instances as inst
from sc.run.status_store import set_action, write_status

PID_FILE = "sc_auto.pid"


def pid_path() -> Path:
    return cursor_config_dir() / PID_FILE


def pid_alive(pid: int) -> bool:
    return inst._pid_alive(pid)  # noqa: SLF001


def read_auto_pid() -> Optional[int]:
    path = pid_path()
    if not path.exists():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    if pid_alive(pid):
        return pid
    path.unlink(missing_ok=True)
    return None


def write_pid() -> None:
    cursor_config_dir().mkdir(parents=True, exist_ok=True)
    pid_path().write_text(str(os.getpid()), encoding="utf-8")


def kill_legacy_exclusive_auto() -> None:
    pid = read_auto_pid()
    if not pid or pid == os.getpid():
        return
    doc = inst.read_instances()
    known = {
        int(info.get("pid") or 0)
        for info in (doc.get("instances") or {}).values()
        if isinstance(info, dict)
    }
    if pid in known:
        return
    try:
        if os.name == "nt":
            import ctypes

            h = ctypes.windll.kernel32.OpenProcess(0x0001, False, int(pid))
            if h:
                ctypes.windll.kernel32.TerminateProcess(h, 1)
                ctypes.windll.kernel32.CloseHandle(h)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass
    pid_path().unlink(missing_ok=True)


def cmd_auto_stop() -> int:
    killed = inst.stop_all_instances()
    pid_path().unlink(missing_ok=True)
    write_status(auto_running=False, auto_pid=None, leader_id=None, instance_count=0)
    set_action("idle", "已停止全部 auto 实例")
    print(f"已停止实例 pids={killed or '-'}")
    return 0


def still_leader(instance_id: str) -> bool:
    try:
        return inst.is_leader(instance_id)
    except Exception:
        return False


def _spawn_background_auto(parent_pid: Optional[int]) -> int:
    import subprocess

    from sc.run.status_store import status_json_path

    creation = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    creation |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    log_path = cursor_config_dir() / "sc_auto.log"
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    args = [sys.executable, "-X", "utf8", "-m", "sc", "auto", "--fg"]
    if parent_pid:
        args.extend(["--parent", str(parent_pid)])
    subprocess.Popen(
        args,
        creationflags=creation,
        close_fds=True,
        stdout=log_f,
        stderr=log_f,
        env=utf8_env(),
    )
    time.sleep(0.4)
    print(f"已后台启动实例 → {inst.instances_json_path()}")
    print(f"状态: {status_json_path()}  日志: {log_path}")
    return 0


def cmd_auto(*, foreground: bool = False, parent_pid: Optional[int] = None) -> int:
    if not foreground and os.name == "nt":
        return _spawn_background_auto(parent_pid)
    from sc.run.autoloop import run_auto_foreground

    return run_auto_foreground(parent_pid=parent_pid)
