"""Declarative base for the application database (projects/documents/...).

Alembic's env.py imports Base.metadata as the migration target -- every
app-db model must be imported somewhere that ends up importing this module
before autogenerate runs (see prometheus.db.models).
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
