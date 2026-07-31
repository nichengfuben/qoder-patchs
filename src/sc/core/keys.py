from __future__ import annotations

"""对齐 Common/client.py ``KeyPool`` / Key 日用量切换（``switch_threshold``）。"""

import time
from dataclasses import dataclass
from typing import List, Optional


def mask_key(key: str) -> str:
    return f"{key[:6]}...{key[-4:]}" if len(key) > 10 else key


@dataclass
class KeyState:
    key: str
    name: str = ""
    is_active: bool = True
    daily_used: Optional[int] = None
    daily_limit: Optional[int] = None
    rpm: Optional[int] = None
    total_used: Optional[int] = None
    last_checked: float = 0.0
    errors: int = 0

    def masked(self) -> str:
        return mask_key(self.key)


class KeyPool:
    """``switch_threshold`` 管 Key 日用量轮换；Cursor 账号换号用 ``usage_threshold``。"""

    def __init__(self, keys: List[str], threshold: int, refresh_interval: int):
        self._states: List[KeyState] = [KeyState(key=k) for k in keys]
        self._idx = 0
        self.threshold = threshold
        self.refresh_interval = refresh_interval

    @property
    def current(self) -> Optional[KeyState]:
        return self._states[self._idx] if self._states else None

    def all(self) -> List[KeyState]:
        return list(self._states)

    def is_empty(self) -> bool:
        return not self._states

    def switch_next(self) -> Optional[KeyState]:
        if not self._states:
            return None
        self._idx = (self._idx + 1) % len(self._states)
        return self.current

    def is_stale(self, s: KeyState) -> bool:
        return (time.time() - s.last_checked) >= self.refresh_interval

    def should_switch(self, s: KeyState) -> bool:
        if s.daily_used is None:
            return False
        if not s.is_active:
            return True
        if s.daily_limit is not None and s.daily_used >= s.daily_limit:
            return True
        return s.daily_used >= self.threshold

    def to_key_list(self) -> List[str]:
        return [s.key for s in self._states]
