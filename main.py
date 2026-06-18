#!/usr/bin/env python3
"""Qoder Patch Manager - Entry point."""
import sys
from pathlib import Path

# Ensure src/ is in Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from qoder_patchs.cli.app import typer_app

if __name__ == "__main__":
    typer_app()
