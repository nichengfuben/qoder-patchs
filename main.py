#!/usr/bin/env python3
"""AgentCLI Patchs - Entry point."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from cli.app import typer_app

if __name__ == "__main__":
    typer_app()
