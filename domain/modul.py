"""Modul und Semester.

Ein Modul gehört dem Studiengang (Komposition über den Modulkatalog) und ist
höchstens einem Semester zugeordnet (Aggregation 0..1). Das Semester hält
deshalb nur Verweise auf Module, die auch ohne es weiterbestehen.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from domain.pruefungsleistung import Pruefungsleistung


class Modul:
    def __init__(self, kuerzel: str, bezeichnung: str, ects: int,
                 pruefungsleistung: Pruefungsleistung) -> None:
        if not kuerzel.strip():
            raise ValueError("Ein Modul braucht ein Kürzel")
        if not 1 <= ects <= 30:
            raise ValueError(f"{ects} ECTS sind für ein Modul ungültig")
        self._kuerzel = kuerzel
        self._bezeichnung = bezeichnung
        self._ects = ects
        self._pruefungsleistung = pruefungsleistung      # Komposition 1:1

    @property
    def kuerzel(self) -> str:
        return self._kuerzel

    @property
    def bezeichnung(self) -> str:
        return self._bezeichnung

    @property
    def ects(self) -> int:
        return self._ects

    @property
    def pruefungsleistung(self) -> Pruefungsleistung:
        return self._pruefungsleistung

    def ist_bestanden(self) -> bool:
        return self._pruefungsleistung.ist_bestanden()

    def note(self) -> Decimal | None:
        return self._pruefungsleistung.note

    def __repr__(self) -> str:
        return f"Modul({self._kuerzel!r}, {self._bezeichnung!r})"


class Semester:
    def __init__(self, nummer: int, beginn: date, ende: date) -> None:
        if nummer < 1:
            raise ValueError("Semester werden ab 1 gezählt")
        if ende <= beginn:
            raise ValueError("Ein Semester endet nach seinem Beginn")
        self._nummer = nummer
        self._beginn = beginn
        self._ende = ende
        self._module: list[Modul] = []                   # Aggregation

    @property
    def nummer(self) -> int:
        return self._nummer

    @property
    def beginn(self) -> date:
        return self._beginn

    @property
    def ende(self) -> date:
        """Letzter Tag des Semesters."""
        return self._ende

    @property
    def module(self) -> tuple[Modul, ...]:
        return tuple(self._module)

    def zugeordnete_ects(self) -> int:
        return sum(m.ects for m in self._module)

    def ist_abgeschlossen(self, stichtag: date) -> bool:
        return stichtag > self._ende

    def enthaelt(self, stichtag: date) -> bool:
        return self._beginn <= stichtag <= self._ende

    def modul_zuordnen(self, modul: Modul) -> None:
        if any(m is modul for m in self._module):
            raise ValueError(f"{modul.bezeichnung} ist dem {self._nummer}. Semester "
                             "bereits zugeordnet")
        self._module.append(modul)

    def modul_entfernen(self, modul: Modul) -> None:
        for i, m in enumerate(self._module):
            if m is modul:
                del self._module[i]
                return
        raise ValueError(f"{modul.bezeichnung} gehört nicht zum {self._nummer}. Semester")
