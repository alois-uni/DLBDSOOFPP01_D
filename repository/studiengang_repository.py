"""Abstrakte Datenhaltung und ihre Umsetzung im Speicher.

Der Controller kennt nur StudiengangRepository (Dependency Inversion,
Phase 2, Abschnitt 2.2). Welche Umsetzung er bekommt, entscheidet allein
DashboardApp bzw. ein Test.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain import Studiengang


class StudiengangRepository(ABC):
    """Schnittstelle der Datenhaltung: den ganzen Studiengang laden und speichern.

    Gespeichert wird immer der vollständige Stand, nie eine einzelne
    Änderung; Kennzahlen werden nicht gespeichert, sondern bei jeder Anzeige
    neu berechnet.
    """

    @abstractmethod
    def lade(self) -> Studiengang:
        """Liefert den gespeicherten Studiengang mit allen Teilen."""

    @abstractmethod
    def speichere(self, sg: Studiengang) -> None:
        """Speichert den Studiengang mit allen Teilen."""


class InMemoryStudiengangRepository(StudiengangRepository):
    """Hält den Studiengang nur im Speicher; für die unittest-Tests."""

    def __init__(self, studiengang: Studiengang) -> None:
        self._studiengang = studiengang
        self.anzahl_speichervorgaenge = 0      # damit Tests das Speichern prüfen können

    def lade(self) -> Studiengang:
        return self._studiengang

    def speichere(self, sg: Studiengang) -> None:
        self._studiengang = sg
        self.anzahl_speichervorgaenge += 1
