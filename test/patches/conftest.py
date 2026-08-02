"""Pytest fixtures for cursor-agent patch tests."""

from __future__ import annotations

import pytest

from test.patches.cursoragent.helpers import load_virgin_index, load_virgin_uichunk


@pytest.fixture(scope="module")
def virgin_index() -> str:
    return load_virgin_index()


@pytest.fixture(scope="module")
def virgin_uichunk() -> str:
    return load_virgin_uichunk()
