from __future__ import annotations

import json


def test_request_continue_nudge(tmp_path, monkeypatch) -> None:
    from sc.run import nudge

    monkeypatch.setattr(nudge, "sc_home_dir", lambda: tmp_path)
    path = nudge.request_continue_nudge("继续")
    assert path == tmp_path / "sc_nudge.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["action"] == "continue"
    assert doc["text"] == "继续"
    assert int(doc["ts"]) > 0
