# Patch Development Guide / 补丁开发指南

This guide walks you through creating a new patch for qoder-patchs, from initial setup to testing and registration.
本指南带你从零开始为 qoder-patchs 创建新补丁, 包括初始设置, 测试和注册.

---

## Overview / 概述

Every patch in qoder-patchs is a Python class that inherits from `PatchBase` and implements four abstract members:
qoder-patchs 中的每个补丁都是一个继承 `PatchBase` 的 Python 类, 需实现四个抽象成员:

| Member | Type | Description | 说明 |
|--------|------|-------------|------|
| `metadata` | property | Returns `PatchMetadata` descriptor | 返回补丁描述信息 |
| `check()` | method | Inspects files, returns `PatchStatus` | 检查文件, 返回补丁状态 |
| `apply()` | method | Applies the patch to target files | 将补丁应用到目标文件 |
| `rollback()` | method | Restores files from backup | 从备份恢复文件 |

---

## Step-by-Step: Creating a New Patch / 分步创建新补丁

### Step 1: Create the Module / 创建模块

Create a new file in `src/qoder_patchs/patches/`:
在 `src/qoder_patchs/patches/` 中创建新文件:

```
src/qoder_patchs/patches/my_patch.py
```

Use snake_case naming. Avoid leading underscores (`_`) -- those are excluded from auto-discovery.
使用 snake_case 命名. 避免前导下划线 (`_`) -- 前导下划线的模块不会被自动发现.

### Step 2: Implement the Patch Class / 实现补丁类

```python
"""My custom patch description."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from qoder_patchs.core.patch_base import (
    PatchBase,
    PatchMetadata,
    PatchResult,
    PatchStatus,
)


class MyPatch(PatchBase):
    """Brief description of what this patch does."""

    @property
    def metadata(self) -> PatchMetadata:
        return PatchMetadata(
            name="my-patch",                    # Unique kebab-case ID
            display_name="My Custom Patch",      # Human-readable name
            description="What this patch does.",  # Detailed description
            version="1.0.0",                     # Semantic version
            author="your-name",                  # Author
            target_files=("target-file.js",),    # Files to modify
            min_cli_version=None,                # Min compatible CLI
            max_cli_version=None,                # Max compatible CLI
            tags=("custom", "feature"),          # Category tags
            reversible=True,                     # Supports rollback?
        )

    def check(self, bundle_dir: Path) -> PatchStatus:
        """Check whether the patch is applied (read-only)."""
        results: list[bool] = []

        for fname in self.metadata.target_files:
            fpath = bundle_dir / fname
            if not fpath.exists():
                continue

            content = fpath.read_text(encoding="utf-8", errors="ignore")

            # Look for a marker that indicates the patch is applied
            is_patched = "some-patch-marker" in content
            results.append(is_patched)

        if not results:
            return PatchStatus.UNKNOWN
        if all(results):
            return PatchStatus.APPLIED
        if any(results):
            return PatchStatus.PARTIAL
        return PatchStatus.NOT_APPLIED

    def apply(self, bundle_dir: Path, dry_run: bool = False) -> PatchResult:
        """Apply the patch to target files."""
        start = time.monotonic()
        files_modified: list[Path] = []
        backups_created: list[Path] = []
        failed_count = 0

        for fname in self.metadata.target_files:
            fpath = bundle_dir / fname
            if not fpath.exists():
                logger.warning("Target file missing: {}", fpath)
                continue

            content = fpath.read_text(encoding="utf-8", errors="ignore")

            # Check if already patched
            if "some-patch-marker" in content:
                logger.info("{} already patched, skipping", fname)
                continue

            if dry_run:
                logger.info("[dry-run] Would patch {}", fpath)
                files_modified.append(fpath)
                continue

            # Create backup
            timestamp = time.strftime("%Y%m%d%H%M%S")
            backup = fpath.with_suffix(fpath.suffix + f".bak.{timestamp}")
            backup.write_text(content, encoding="utf-8")
            backups_created.append(backup)

            # Perform the replacement
            patched = content.replace("original-text", "replacement-text")

            # Verify the replacement worked
            if "replacement-text" not in patched:
                logger.error("Patch verification failed for {}", fname)
                fpath.write_text(content, encoding="utf-8")  # Restore
                failed_count += 1
                continue

            fpath.write_text(patched, encoding="utf-8")
            files_modified.append(fpath)

        status = PatchStatus.APPLIED if failed_count == 0 else PatchStatus.FAILED
        if dry_run:
            status = PatchStatus.NOT_APPLIED

        return PatchResult(
            status=status,
            message=f"Patched {len(files_modified)} file(s)" if not dry_run else "[dry-run]",
            patch_name=self.metadata.name,
            files_modified=files_modified,
            backups_created=backups_created,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    def rollback(
        self, bundle_dir: Path, backup_path: Optional[Path] = None
    ) -> PatchResult:
        """Restore target files from backup."""
        start = time.monotonic()
        restored: list[Path] = []

        for fname in self.metadata.target_files:
            fpath = bundle_dir / fname

            if backup_path and backup_path.exists():
                fpath.write_text(
                    backup_path.read_text(encoding="utf-8"), encoding="utf-8"
                )
                restored.append(fpath)
                continue

            # Find most recent backup
            backups = sorted(
                bundle_dir.glob(f"{fname}.bak.*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if backups:
                fpath.write_text(
                    backups[0].read_text(encoding="utf-8"), encoding="utf-8"
                )
                restored.append(fpath)

        return PatchResult(
            status=PatchStatus.NOT_APPLIED if restored else PatchStatus.FAILED,
            message=f"Rolled back {len(restored)} file(s)" if restored else "No backups found",
            patch_name=self.metadata.name,
            files_modified=restored,
            duration_ms=(time.monotonic() - start) * 1000,
        )
```

### Step 3: Register the Patch / 注册补丁

Two options:
两种方式:

**Option A: Built-in (auto-discovery) / 内置 (自动发现)**

Import the class in `src/qoder_patchs/patches/__init__.py`:
在 `src/qoder_patchs/patches/__init__.py` 中导入:

```python
from qoder_patchs.patches.my_patch import MyPatch

__all__ = ["Win10WarningPatch", "MyPatch"]
```

The registry will automatically discover it via `pkgutil`.
注册表会通过 `pkgutil` 自动发现.

**Option B: Entry Point / 入口点注册**

Add to `pyproject.toml`:
添加到 `pyproject.toml`:

```toml
[project.entry-points."qoder_patchs.patches"]
my-patch = "qoder_patchs.patches.my_patch:MyPatch"
```

This is also how third-party packages register external patches.
这也是第三方包注册外部补丁的方式.

### Step 4: Verify Discovery / 验证发现

```bash
python -c "
from qoder_patchs.core.registry import PatchRegistry
r = PatchRegistry()
r.discover_builtin()
print('Registered patches:', r.names())
"
```

---

## PatchBase Interface Reference / PatchBase 接口参考

### PatchMetadata Fields / PatchMetadata 字段

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Unique kebab-case identifier (e.g., `"win10-warning"`) |
| `display_name` | `str` | Yes | Human-readable name for CLI display |
| `description` | `str` | Yes | Detailed description of the patch |
| `version` | `str` | Yes | Semantic version string (e.g., `"2.0.0"`) |
| `author` | `str` | Yes | Patch author name |
| `target_files` | `tuple[str, ...]` | Yes | Tuple of target file names |
| `min_cli_version` | `str | None` | No | Minimum compatible CLI version |
| `max_cli_version` | `str | None` | No | Maximum compatible CLI version |
| `tags` | `tuple[str, ...]` | No | Category tags (default: `()`) |
| `reversible` | `bool` | No | Whether rollback is supported (default: `True`) |

### PatchStatus Enum / PatchStatus 枚举

| Value | Meaning |
|-------|---------|
| `NOT_APPLIED` | Patch has not been applied |
| `APPLIED` | Patch successfully applied to all targets |
| `FAILED` | Patch application failed |
| `PARTIAL` | Applied to some but not all targets |
| `UNKNOWN` | Status cannot be determined |

### PatchResult Fields / PatchResult 字段

| Field | Type | Description |
|-------|------|-------------|
| `status` | `PatchStatus` | Resulting patch status |
| `message` | `str` | Human-readable summary |
| `patch_name` | `str` | Patch name that was executed |
| `files_modified` | `list[Path]` | Files that were modified |
| `backups_created` | `list[Path]` | Backup files created |
| `duration_ms` | `float` | Operation duration in milliseconds |
| `error` | `str | None` | Error message if failed |
| `timestamp` | `datetime` | When the operation completed |

**Computed property**: `result.success` returns `True` when `status == PatchStatus.APPLIED`.

### Concrete Methods / 具体方法

`PatchBase` provides two concrete methods:

- **`validate(bundle_dir)`** -- Checks that all target files exist and are writable. Returns a list of issue strings (empty = no issues).
- **`info()`** -- Returns a formatted multi-line string summarizing the patch metadata.

---

## Helper Utilities / 辅助工具

The `_templates.py` module provides reusable helpers:
`_templates.py` 模块提供可复用的辅助函数:

```python
from qoder_patchs.patches._templates import (
    read_file_text,        # UTF-8 file reader
    create_inline_backup,  # Timestamped backup creator
    safe_regex_replace,    # Regex replace with verification
)
```

For production patches, prefer using `BackupManager`:
生产环境补丁建议使用 `BackupManager`:

```python
from qoder_patchs.utils.backup import BackupManager

bm = BackupManager(keep_count=3)
backup_path = bm.create_backup(fpath)
bm.cleanup_old_backups(fpath)
```

---

## Testing Patches / 测试补丁

### Unit Test Structure / 单元测试结构

Create tests in `test/patches/test_my_patch.py`:
在 `test/patches/test_my_patch.py` 创建测试:

```python
"""Tests for MyPatch."""

import pytest
from pathlib import Path
from qoder_patchs.patches.my_patch import MyPatch
from qoder_patchs.core.patch_base import PatchStatus


class TestMyPatch:
    """Test suite for MyPatch."""

    @pytest.fixture
    def patch(self):
        return MyPatch()

    @pytest.fixture
    def bundle_dir(self, tmp_path):
        """Create a temporary bundle directory with test files."""
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        # Create mock target files
        (bundle / "target-file.js").write_text(
            "original content here", encoding="utf-8"
        )
        return bundle

    def test_metadata(self, patch):
        """Verify metadata is correct."""
        meta = patch.metadata
        assert meta.name == "my-patch"
        assert meta.version == "1.0.0"
        assert "target-file.js" in meta.target_files

    def test_check_not_applied(self, patch, bundle_dir):
        """Check returns NOT_APPLIED for unpatched files."""
        status = patch.check(bundle_dir)
        assert status == PatchStatus.NOT_APPLIED

    def test_apply_success(self, patch, bundle_dir):
        """Apply patch successfully."""
        result = patch.apply(bundle_dir)
        assert result.success
        assert len(result.files_modified) > 0
        assert len(result.backups_created) > 0

    def test_apply_dry_run(self, patch, bundle_dir):
        """Dry run does not modify files."""
        original = (bundle_dir / "target-file.js").read_text(encoding="utf-8")
        result = patch.apply(bundle_dir, dry_run=True)
        current = (bundle_dir / "target-file.js").read_text(encoding="utf-8")
        assert original == current

    def test_apply_already_patched(self, patch, bundle_dir):
        """Skip files that are already patched."""
        patch.apply(bundle_dir)
        result = patch.apply(bundle_dir)  # Second apply
        assert result.success

    def test_rollback(self, patch, bundle_dir):
        """Rollback restores original content."""
        original = (bundle_dir / "target-file.js").read_text(encoding="utf-8")
        patch.apply(bundle_dir)
        result = patch.rollback(bundle_dir)
        assert result.success
        restored = (bundle_dir / "target-file.js").read_text(encoding="utf-8")
        assert restored == original

    def test_validate(self, patch, bundle_dir):
        """Validate returns no issues for valid bundle."""
        issues = patch.validate(bundle_dir)
        assert issues == []

    def test_validate_missing_file(self, patch, tmp_path):
        """Validate reports missing target files."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        issues = patch.validate(empty_dir)
        assert len(issues) > 0
```

### Running Tests / 运行测试

```bash
# Run tests for a specific patch / 运行特定补丁的测试
pytest test/patches/test_my_patch.py -v

# Run all tests / 运行所有测试
pytest

# Run with coverage / 带覆盖率运行
pytest --cov=qoder_patchs --cov-report=term-missing
```

---

## Best Practices / 最佳实践

1. **Always create backups** before modifying files. Use `BackupManager` for production code or `create_inline_backup()` for simple patches.

2. **Verify replacements** after applying. Use regex search to confirm the expected text is present in the patched content.

3. **Handle dry_run** by simulating the operation without modifying files. Return a `PatchResult` with `status=NOT_APPLIED`.

4. **Use `encoding="utf-8", errors="ignore"`** when reading bundle files -- they may contain non-UTF-8 sequences.

5. **Support rollback** by setting `reversible=True` in metadata and implementing the `rollback()` method.

6. **Use `loguru.logger`** for all logging. Avoid `print()` statements.

7. **Keep patches idempotent** -- applying the same patch twice should be safe (check for already-applied state).

8. **Write tests** covering: metadata, check (all states), apply, dry-run, already-applied, rollback, validate.

---

## Checklist / 检查清单

- [ ] Created `src/qoder_patchs/patches/<name>.py`
- [ ] Class inherits from `PatchBase`
- [ ] `metadata` returns `PatchMetadata` with unique name and correct target files
- [ ] `check()` inspects files and returns appropriate `PatchStatus`
- [ ] `apply()` creates backups before modifying files
- [ ] `apply()` verifies replacements took effect
- [ ] `apply()` handles `dry_run=True` correctly
- [ ] `rollback()` restores from backup
- [ ] Registered via `patches/__init__.py` or entry point
- [ ] Tests in `test/patches/test_<name>.py`
- [ ] All tests pass: `pytest`
