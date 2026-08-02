from __future__ import annotations

"""Node vm.Script syntax check helpers for patched JS bundles."""

import subprocess
import tempfile
from pathlib import Path


def js_syntax_checker_scripts() -> tuple[tuple[str, str], ...]:
    return (
        (
            "wrap",
            "const fs=require('fs');const vm=require('vm');const Module=require('module');\n"
            "try{new vm.Script(Module.wrap(fs.readFileSync(process.argv[2],'utf8')));}\n"
            "catch(e){console.error(String(e&&e.message||e));process.exit(1)}\n",
        ),
        (
            "bare",
            "const fs=require('fs');const vm=require('vm');\n"
            "try{new vm.Script(fs.readFileSync(process.argv[2],'utf8'));}\n"
            "catch(e){console.error(String(e&&e.message||e));process.exit(1)}\n",
        ),
    )


def run_js_syntax_checker(
    node_exe: Path, target_path: str, mode: str, checker_src: str
) -> None:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as chk:
        chk.write(checker_src)
        checker_path = chk.name
    try:
        proc = subprocess.run(
            [str(node_exe), checker_path, target_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip().splitlines()
            msg = err[0] if err else "unknown syntax error"
            raise RuntimeError(f"JS syntax check failed ({mode}): {msg}")
    finally:
        Path(checker_path).unlink(missing_ok=True)
