from __future__ import annotations

"""Backward-compatible entry for old ``sc-statusline.cmd`` (``-m sc.statusline_fast``).

Logic lives in ``sc.run.status_store``; this module only re-exports ``run`` / ``main``.
"""

from sc.run.status_store import main, run

__all__ = ["main", "run"]

if __name__ == "__main__":
    main()
