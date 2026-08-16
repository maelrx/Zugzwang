"""Zugzwang runtime package."""

from pathlib import Path

__version__ = "0.1.0.dev0"

migration_dir = Path(__file__).resolve().parent / "persistence" / "migrations"
