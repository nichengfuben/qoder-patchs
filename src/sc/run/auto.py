from __future__ import annotations

"""Multi-instance auto loop: leader election + usage polling + supervisor."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from sc.core.paths import migrate_legacy_sc_home, sc_home_dir
from sc.core.encoding import utf8_env
from sc.run import instances as inst
from sc.run.status_store import set_action, write_status

PID_FILE = "sc_auto.pid"
STOP_FILE = "sc_auto.stop"
ENSURE_COOLDOWN_FILE = "sc_auto.ensure.ts"
SUPERVISOR_RESTART_SEC = 3.0
ENSURE_COOLDOWN_SEC = 30.0


def peek_instances() -> Dict[str, Any]:
    try:
        with inst._file_lock():  # noqa: SLF001
            return inst._read_unlocked()  # noqa: SLF001
    except Exception:
        return inst._empty()  # noqa: SLF001


def leader_active_peek(*, now: Optional[float] = None) -> bool:
    doc = peek_instances()
    lid = doc.get("leader_id")
    if not lid:
        return False
    info = (doc.get("instances") or {}).get(lid)
    if not isinstance(info, dict):
        return False
    return inst._instance_active(info, now=now)  # noqa: SLF001


def pid_path() -> Path:
    migrate_legacy_sc_home()
    return sc_home_dir() / PID_FILE


def stop_path() -> Path:
    migrate_legacy_sc_home()
    return sc_home_dir() / STOP_FILE


def ensure_cooldown_path() -> Path:
    migrate_legacy_sc_home()
    return sc_home_dir() / ENSURE_COOLDOWN_FILE


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
    sc_home_dir().mkdir(parents=True, exist_ok=True)
    pid_path().write_text(str(os.getpid()), encoding="utf-8")


def request_auto_stop() -> None:
    sc_home_dir().mkdir(parents=True, exist_ok=True)
    stop_path().write_text(str(time.time()), encoding="utf-8")


def clear_auto_stop() -> None:
    try:
        stop_path().unlink(missing_ok=True)
    except Exception:
        pass


def should_auto_stop() -> bool:
    return stop_path().is_file()


def _ensure_on_cooldown() -> bool:
    path = ensure_cooldown_path()
    if not path.is_file():
        return False
    try:
        ts = float(path.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    return (time.time() - ts) < ENSURE_COOLDOWN_SEC


def _touch_ensure_cooldown() -> None:
    sc_home_dir().mkdir(parents=True, exist_ok=True)
    ensure_cooldown_path().write_text(str(time.time()), encoding="utf-8")


def kill_legacy_exclusive_auto() -> None:
    pid = read_auto_pid()
    if not pid or pid == os.getpid():
        return
    doc = peek_instances()
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


def _terminate_pid(pid: int) -> None:
    if pid <= 0 or not pid_alive(pid) or pid == os.getpid():
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


def cmd_auto_stop() -> int:
    request_auto_stop()
    killed = inst.stop_all_instances()
    sup = read_auto_pid()
    if sup and sup != os.getpid():
        _terminate_pid(sup)
    pid_path().unlink(missing_ok=True)
    write_status(auto_running=False, auto_pid=None, leader_id=None, instance_count=0)
    set_action("idle", "已停止全部 auto 实例")
    print(f"已停止实例 pids={killed or '-'}")
    return 0


def still_leader(instance_id: str) -> bool:
    """确认仍是 leader。先心跳再检查，避免换号/查用量阻塞超过 STALE_SEC 被自我踢下线。"""
    try:
        doc = inst.heartbeat(instance_id)
        return bool(doc.get("leader_id") == instance_id)
    except Exception:
        return False


def _win_creationflags(*, detached: bool = True) -> int:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    if detached:
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    return flags


def _spawn_background_auto(parent_pid: Optional[int]) -> int:
    from sc.run.status_store import status_json_path

    log_path = sc_home_dir() / "sc_auto.log"
    log_f = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
    args = [sys.executable, "-X", "utf8", "-m", "sc", "auto", "--supervise"]
    if parent_pid:
        args.extend(["--parent", str(parent_pid)])
    kwargs = {
        "args": args,
        "close_fds": True,
        "stdout": log_f,
        "stderr": log_f,
        "env": utf8_env(),
    }
    if os.name == "nt":
        kwargs["creationflags"] = _win_creationflags(detached=True)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(**kwargs)
    time.sleep(0.4)
    print(f"已后台启动 supervisor → {inst.instances_json_path()}")
    print(f"状态: {status_json_path()}  日志: {log_path}")
    return 0


def ensure_auto_running(*, parent_pid: Optional[int] = None) -> bool:
    """无 supervisor / leader 时拉起 sc auto；挂死进程会被终止并重启。"""
    return maybe_recover_auto(parent_pid=parent_pid)


def maybe_recover_auto(*, parent_pid: Optional[int] = None) -> bool:
    """STALE / 进程死亡 / 挂起时自动拉起 supervisor（30s cooldown）。"""
    if should_auto_stop():
        return False
    if _ensure_on_cooldown():
        return False

    sup = read_auto_pid()
    if sup and pid_alive(sup):
        if leader_active_peek():
            return False
        print(f"sc auto: supervisor pid={sup} 无心跳，终止并重启", flush=True)
        _terminate_pid(sup)
        try:
            pid_path().unlink(missing_ok=True)
        except Exception:
            pass
    elif leader_active_peek():
        return False

    clear_auto_stop()
    _spawn_background_auto(parent_pid)
    _touch_ensure_cooldown()
    return True


WORKER_START_GRACE_SEC = 30.0
WATCH_POLL_SEC = 2.0


def _worker_heartbeat_stale(worker_pid: int) -> bool:
    doc = peek_instances()
    lid = doc.get("leader_id")
    if not lid:
        return False
    info = (doc.get("instances") or {}).get(lid)
    if not isinstance(info, dict):
        return False
    if int(info.get("pid") or 0) != worker_pid:
        return False
    hb = float(info.get("heartbeat_at") or 0)
    if hb <= 0:
        return True
    return (time.time() - hb) >= inst.STALE_GRACE_SEC


def _spawn_foreground_worker(log_f) -> subprocess.Popen:
    args = [sys.executable, "-X", "utf8", "-m", "sc", "auto", "--fg"]
    kwargs: dict = {
        "args": args,
        "stdout": log_f,
        "stderr": log_f,
        "env": utf8_env(),
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return subprocess.Popen(**kwargs)


def _supervise_worker(proc: subprocess.Popen, *, started_at: float) -> int:
    while proc.poll() is None:
        if should_auto_stop():
            proc.terminate()
            break
        if (
            time.time() - started_at >= WORKER_START_GRACE_SEC
            and _worker_heartbeat_stale(proc.pid)
        ):
            print(f"supervisor: worker pid={proc.pid} 心跳超时，终止", flush=True)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            break
        time.sleep(WATCH_POLL_SEC)
    try:
        return int(proc.wait(timeout=1))
    except Exception:
        proc.kill()
        return int(proc.wait())


def run_auto_supervisor(*, parent_pid: Optional[int] = None) -> int:
    """守护进程：worker 子进程 + 心跳看门狗，挂死可杀后重启。"""
    clear_auto_stop()
    prev = read_auto_pid()
    if prev and prev != os.getpid() and pid_alive(prev):
        _terminate_pid(prev)
    write_pid()
    log_path = sc_home_dir() / "sc_auto.log"
    print(f"supervisor 启动 pid={os.getpid()} log={log_path}", flush=True)
    with open(log_path, "a", encoding="utf-8") as log_f:
        while not should_auto_stop():
            if parent_pid and not pid_alive(parent_pid):
                print("supervisor: parent 已退出，停止", flush=True)
                break
            started = time.time()
            try:
                proc = _spawn_foreground_worker(log_f)
            except Exception as exc:
                print(f"supervisor: 启动 worker 失败: {exc}", flush=True)
                time.sleep(SUPERVISOR_RESTART_SEC)
                continue
            code = _supervise_worker(proc, started_at=started)
            if should_auto_stop():
                break
            print(
                f"supervisor: worker 退出 code={code}，{SUPERVISOR_RESTART_SEC}s 后重启",
                flush=True,
            )
            time.sleep(SUPERVISOR_RESTART_SEC)
    try:
        if read_auto_pid() == os.getpid():
            pid_path().unlink(missing_ok=True)
    except Exception:
        pass
    print("supervisor 已停止", flush=True)
    return 0


def cmd_auto(
    *,
    foreground: bool = False,
    supervise: bool = False,
    parent_pid: Optional[int] = None,
) -> int:
    if supervise:
        return run_auto_supervisor(parent_pid=parent_pid)
    if foreground:
        from sc.run.autoloop import run_auto_foreground

        return run_auto_foreground(parent_pid=parent_pid, fg_worker=True)
    sup = read_auto_pid()
    if sup and pid_alive(sup):
        print(f"supervisor 已在运行 pid={sup}")
        return 0
    clear_auto_stop()
    return _spawn_background_auto(parent_pid)


def fetch_usage_parsed(token: str, *, timeout: float, instance_id: str) -> dict:
    """查用量并在阻塞期间持续 heartbeat，避免 statusline STALE。"""
    import threading
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
    from contextlib import contextmanager
    from typing import Iterator

    from sc.core import api

    @contextmanager
    def _heartbeat_while() -> Iterator[None]:
        stop = threading.Event()

        def _loop() -> None:
            while not stop.wait(2.0):
                try:
                    inst.heartbeat(instance_id)
                except Exception:
                    pass

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()

    with _heartbeat_while():
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(api.fetch_usage, token, timeout=timeout)
            try:
                raw = fut.result(timeout=timeout + 10.0)
            except FutTimeout:
                raise RuntimeError("超时") from None
    return api.parse_usage(raw)
