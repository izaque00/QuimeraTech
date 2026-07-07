"""
Quimera MarkX — Entry point module.

This is the official entry point declared in pyproject.toml:
    [tool.poetry.scripts]
    quimera = "quimera.main:main"

Delegates to the unified CLI in quimera.cli.
"""

from quimera.cli import main

__all__ = ["main"]

if __name__ == "__main__":
    main()
