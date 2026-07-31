from __future__ import annotations

"""多 AgentCLI 实例心跳与单 leader 选举（~/.cursor/sc_instances.json）。"""

import json
import os
import socket
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


INSTANCES_FILE = "sc_instances.json"
LOCK_FILE = "sc_instances.lock"
STALE_SEC = 10.0
HEARTBEAT_SEC = 2.0
SCHEMA_VERSION = 1


def _is_stale(ts: float, *, now: Optional[float] = None) -> bool:
    now = time.time() if now is None else now
    try:
        t = float(ts or 0)
    except Exception:
        return True
    if t <= 0:
        return True
    return (now - t) >= STALE_SEC


def home_cursor_dir() -> Path:
    return Path.home() / ".cursor"


def instances_json_path() -> Path:
    return home_cursor_dir() / INSTANCES_FILE


def _lock_path() -> Path:
    return home_cursor_dir() / LOCK_FILE


def new_instance_id() -> str:
    if hasattr(uuid, "uuid7"):
        return str(uuid.uuid7())
    return f"{int(time.time() * 1000):013x}-{uuid.uuid4()}"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _try_acquire_lock(fh, deadline: float, path: Path) -> bool:
    if os.name == "nt":
        import msvcrt

        while True:
            try:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                if time.time() >= deadline:
                    raise TimeoutError(f"lock timeout: {path}")
                time.sleep(0.05)
    import fcntl

    while True:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.time() >= deadline:
                raise TimeoutError(f"lock timeout: {path}")
            time.sleep(0.05)


def _release_lock(fh) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


@contextmanager
def _file_lock(timeout: float = 5.0) -> Iterator[None]:
    home_cursor_dir().mkdir(parents=True, exist_ok=True)
    path = _lock_path()
    fh = open(path, "a+b")
    deadline = time.time() + timeout
    locked = False
    try:
        locked = _try_acquire_lock(fh, deadline, path)
        yield
    finally:
        if locked:
            _release_lock(fh)
        fh.close()


def _empty() -> Dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "instances": {},
        "leader_id": None,
        "usage": {},
        "updated_at": time.time(),
    }


def _read_unlocked() -> Dict[str, Any]:
    path = instances_json_path()
    if not path.exists():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _empty()
        data.setdefault("version", SCHEMA_VERSION)
        data.setdefault("instances", {})
        data.setdefault("leader_id", None)
        data.setdefault("usage", {})
        if not isinstance(data["instances"], dict):
            data["instances"] = {}
        return data
    except Exception:
        return _empty()


def _write_unlocked(data: Dict[str, Any]) -> None:
    home_cursor_dir().mkdir(parents=True, exist_ok=True)
    path = instances_json_path()
    data["updated_at"] = time.time()
    data["updated_iso"] = time.strftime("%Y-%m-%d %H:%M:%S")
    text = json.dumps(data, ensure_ascii=False, indent=2)
    # 文件锁内仍用唯一 tmp，避免残留 .tmp 与偶发跨进程冲突
    tmp = path.with_name(f"sc_instances.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        path.write_text(text, encoding="utf-8")


def _fresh_entries(
    data: Dict[str, Any], *, now: Optional[float] = None
) -> List[Tuple[float, str, Dict[str, Any]]]:
    now = time.time() if now is None else now
    out: List[Tuple[float, str, Dict[str, Any]]] = []
    for iid, info in (data.get("instances") or {}).items():
        if not isinstance(info, dict):
            continue
        if _is_stale(float(info.get("heartbeat_at") or 0), now=now):
            continue
        started = float(info.get("started_at") or 0)
        out.append((started, str(iid), info))
    return out


def _prune_by_timestamp(data: Dict[str, Any], *, now: Optional[float] = None) -> List[str]:
    now = time.time() if now is None else now
    removed: List[str] = []
    inst_map = data.get("instances") or {}
    for iid, info in list(inst_map.items()):
        if not isinstance(info, dict):
            inst_map.pop(iid, None)
            removed.append(iid)
            continue
        if _is_stale(float(info.get("heartbeat_at") or 0), now=now):
            inst_map.pop(iid, None)
            removed.append(iid)
    data["instances"] = inst_map
    return removed


def _elect(data: Dict[str, Any], *, now: Optional[float] = None) -> Optional[str]:
    now = time.time() if now is None else now
    fresh = _fresh_entries(data, now=now)
    if not fresh:
        data["leader_id"] = None
        usage = data.get("usage")
        if isinstance(usage, dict) and _is_stale(
            float(usage.get("published_at") or 0), now=now
        ):
            data["usage"] = {}
        for info in (data.get("instances") or {}).values():
            if isinstance(info, dict):
                info["role"] = "follower"
        return None
    fresh.sort(key=lambda x: (-x[0], x[1]))
    leader = fresh[0][1]
    data["leader_id"] = leader
    for iid, info in (data.get("instances") or {}).items():
        if isinstance(info, dict):
            info["role"] = "leader" if iid == leader else "follower"
    # 旧 leader 迟到用量作废
    usage = data.get("usage")
    if isinstance(usage, dict):
        pub_leader = usage.get("leader_id")
        if pub_leader and pub_leader != leader:
            data["usage"] = {}
        elif _is_stale(float(usage.get("published_at") or 0), now=now):
            data["usage"] = {}
    return leader


def mutate(fn) -> Dict[str, Any]:
    with _file_lock():
        data = _read_unlocked()
        fn(data)
        _elect(data)
        _write_unlocked(data)
        return data


def read_instances() -> Dict[str, Any]:
    with _file_lock():
        data = _read_unlocked()
        _elect(data)
        _write_unlocked(data)
        return data


def register_instance(*, parent_pid: Optional[int] = None) -> str:
    iid = new_instance_id()
    now = time.time()

    def _op(data: Dict[str, Any]) -> None:
        data["instances"][iid] = {
            "pid": os.getpid(),
            "parent_pid": parent_pid,
            "started_at": now,
            "heartbeat_at": now,
            "host": socket.gethostname(),
            "role": "follower",
        }

    mutate(_op)
    return iid


def heartbeat(instance_id: str, *, parent_pid: Optional[int] = None) -> Dict[str, Any]:

    def _op(data: Dict[str, Any]) -> None:
        if parent_pid and not _pid_alive(parent_pid):
            data.get("instances", {}).pop(instance_id, None)
            return
        info = (data.get("instances") or {}).get(instance_id)
        if not isinstance(info, dict):
            now = time.time()
            data.setdefault("instances", {})[instance_id] = {
                "pid": os.getpid(),
                "parent_pid": parent_pid,
                "started_at": now,
                "heartbeat_at": now,
                "host": socket.gethostname(),
                "role": "follower",
            }
            return
        info["heartbeat_at"] = time.time()
        info["pid"] = os.getpid()
        if parent_pid is not None:
            info["parent_pid"] = parent_pid

    return mutate(_op)




def unregister(instance_id: str) -> None:
    def _op(data: Dict[str, Any]) -> None:
        data.get("instances", {}).pop(instance_id, None)

    mutate(_op)


def is_leader(instance_id: str, data: Optional[Dict[str, Any]] = None) -> bool:
    doc = data if data is not None else read_instances()
    return bool(doc.get("leader_id") == instance_id)


def online_count(data: Optional[Dict[str, Any]] = None) -> int:
    doc = data if data is not None else read_instances()
    return len(_fresh_entries(doc))


def publish_usage(usage: Dict[str, Any], **extra: Any) -> None:

    def _op(data: Dict[str, Any]) -> None:
        lid = data.get("leader_id")
        cur = dict(data.get("usage") or {})
        for k, v in usage.items():
            if v is not None:
                cur[k] = v
        for k, v in extra.items():
            if v is not None:
                cur[k] = v
        cur["published_at"] = time.time()
        if lid:
            cur["leader_id"] = lid
        data["usage"] = cur

    mutate(_op)


def leader_heartbeat_at(data: Optional[Dict[str, Any]] = None) -> float:
    doc = data if data is not None else read_instances()
    lid = doc.get("leader_id")
    if not lid:
        return 0.0
    info = (doc.get("instances") or {}).get(lid)
    if not isinstance(info, dict):
        return 0.0
    return float(info.get("heartbeat_at") or 0)


def _terminate_pid(pid: int) -> bool:
    if pid <= 0 or not _pid_alive(pid) or pid == os.getpid():
        return False
    try:
        if os.name == "nt":
            import ctypes

            h = ctypes.windll.kernel32.OpenProcess(0x0001, False, pid)
            if not h:
                return False
            ctypes.windll.kernel32.TerminateProcess(h, 1)
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        os.kill(pid, 15)
        return True
    except Exception:
        return False


def stop_all_instances() -> List[int]:
    killed: List[int] = []
    with _file_lock():
        data = _read_unlocked()
        for info in list((data.get("instances") or {}).values()):
            if not isinstance(info, dict):
                continue
            pid = int(info.get("pid") or 0)
            if _terminate_pid(pid):
                killed.append(pid)
        _write_unlocked(_empty())
    return killed


def leader_prune_stale(instance_id: str) -> Dict[str, Any]:
    from sc.run.autoloop import leader_prune_stale as _impl

    return _impl(instance_id)


def follower_clear_stale_leader(instance_id: str) -> Dict[str, Any]:
    from sc.run.autoloop import follower_clear_stale_leader as _impl

    return _impl(instance_id)
