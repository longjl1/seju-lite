"""
Entry point for running seju-lite as a module:
python -m seju_lite
"""

from seju_lite.cli.commands import app


if __name__ == "__main__":
    app()