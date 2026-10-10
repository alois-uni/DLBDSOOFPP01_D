"""Paket repository: Datenhaltung. Kennt nur das Paket domain."""

from repository.sqlite_repository import SqliteStudiengangRepository
from repository.studiengang_repository import (InMemoryStudiengangRepository,
                                               StudiengangRepository)

__all__ = ["StudiengangRepository", "SqliteStudiengangRepository",
           "InMemoryStudiengangRepository"]
