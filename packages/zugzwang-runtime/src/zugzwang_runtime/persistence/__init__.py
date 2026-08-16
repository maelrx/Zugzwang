"""Persistence layer: SQLite WAL + SQLAlchemy Core + Alembic (ADR-012/013).

SQL is confined to this package. Repositories expose small, explicit
statements; domain entities never see SQLAlchemy rows. A single logical
writer owns all writes; readers use WAL-safe connections.
"""

__all__ = []
