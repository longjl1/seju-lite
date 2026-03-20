"""
Backward-compatible entry module.

This module keeps `seju_lite.main:app` importable for older integrations
while delegating to the new CLI implementation.
"""

from seju_lite.cli.commands import app


if __name__ == "__main__":
    app()
