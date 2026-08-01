from __future__ import annotations

"""强制 UTF-8 标准流，避免 Windows GBK 与 Agent UTF-8 互解乱码。"""

import os
import sys


def ensure_utf8_stdio() -> None:
    """进程内尽早调用：环境变量 + stdout/stderr UTF-8（不改 stdin，避免破坏 pytest/管道）。"""
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    try:
        from cli.echotools_bridge import _ensure_windows_console

        _ensure_windows_console()
    except Exception:
        pass
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)  # type: ignore[attr-defined]
            continue
        except Exception:
            pass
        try:
            import io

            buf = getattr(stream, "buffer", None)
            if buf is None:
                continue
            wrapped = io.TextIOWrapper(
                buf,
                encoding="utf-8",
                errors="replace",
                write_through=True,
                line_buffering=True,
            )
            setattr(sys, name, wrapped)
        except Exception:
            pass


def utf8_env(base: dict | None = None) -> dict:
    """给子进程用的环境副本。"""
    env = dict(base or os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env
