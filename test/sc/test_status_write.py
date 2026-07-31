"""Tests for resilient sc_status.json writes under concurrency."""

from __future__ import annotations

import threading
from pathlib import Path

from sc import status_store


def test_write_status_concurrent_no_raise(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(status_store, "cursor_config_dir", lambda: tmp_path)
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            for n in range(20):
                status_store.write_status(total_pct=float(i), usage_seq=n, poll_n=n)
        except BaseException as exc:  # noqa: BLE001 — 收集并发异常
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    st = status_store.read_status()
    assert "total_pct" in st
    assert (tmp_path / "sc_status.json").exists()
    # 不应残留固定名 sc_status.tmp
    assert not (tmp_path / "sc_status.tmp").exists()
