"""Studiengang: Wurzel der Objektstruktur.

Der Studiengang besitzt seine Semester, seinen Modulkatalog und seine
Studienziele (jeweils Komposition). Alles, was das Dashboard anzeigt, lässt
sich von hier aus erreichen; deshalb genügt ein Repository.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from domain.aufzaehlungen import Abschlussgrad
from domain.modul import Modul, Semester
from domain.pruefungsleistung import Pruefungsleistung
from domain.studienziel import Studienziel

MONATE_JE_SEMESTER = 6


def _plus_monate(tag: date, monate: int) -> date:
    """Addiert Kalendermonate; ein 31. wird bei kürzeren Monaten gekürzt."""
    jahr, monat = divmod(tag.month - 1 + monate, 12)
    jahr += tag.year
    monat += 1
    for t in range(tag.day, 27, -1):
        try:
            return date(jahr, monat, t)
        except ValueError:
            continue
    return date(jahr, monat, min(tag.day, 28))


class Studiengang:
    def __init__(self, bezeichnung: str, abschluss: Abschlussgrad, startdatum: date,
                 gesamt_ects: int = 180) -> None:
        if gesamt_ects <= 0:
            raise ValueError("Ein Studiengang braucht ECTS")
        self._bezeichnung = bezeichnung
        self._abschluss = abschluss
        self._startdatum = startdatum
        self._gesamt_ects = gesamt_ects
        self._semester: list[Semester] = []          # Komposition
        self._module: list[Modul] = []               # Komposition (Modulkatalog)
        self._ziele: list[Studienziel] = []          # Komposition

    # ------------------------------------------------------------ Erzeugung
    # Teile entstehen nur über den Studiengang, damit sie nie ohne Besitzer
    # existieren (Komposition, r3).
    def semesterbeginn(self, nummer: int) -> date:
        """Erster Tag des Semesters nummer bei sechs Monaten je Semester."""
        return _plus_monate(self._startdatum, MONATE_JE_SEMESTER * (nummer - 1))

    def neues_semester(self, beginn: date | None = None,
                       ende: date | None = None) -> Semester:
        nummer = len(self._semester) + 1
        beginn = beginn or self.semesterbeginn(nummer)
        ende = ende or self.semesterbeginn(nummer + 1) - timedelta(days=1)
        semester = Semester(nummer, beginn, ende)
        self._semester.append(semester)
        return semester

    def neues_modul(self, kuerzel: str, bezeichnung: str, ects: int,
                    pruefungsleistung: Pruefungsleistung) -> Modul:
        if self.modul(kuerzel) is not None:
            raise ValueError(f"Das Kürzel {kuerzel} ist bereits vergeben")
        modul = Modul(kuerzel, bezeichnung, ects, pruefungsleistung)
        self._module.append(modul)
        return modul

    def neues_ziel(self, ziel: Studienziel) -> Studienziel:
        self._ziele.append(ziel)
        return ziel

    # ------------------------------------------------------------ lesen
    @property
    def bezeichnung(self) -> str:
        return self._bezeichnung

    @property
    def abschluss(self) -> Abschlussgrad:
        return self._abschluss

    @property
    def startdatum(self) -> date:
        return self._startdatum

    @property
    def gesamt_ects(self) -> int:
        return self._gesamt_ects

    @property
    def semester_liste(self) -> tuple[Semester, ...]:
        return tuple(self._semester)

    @property
    def module(self) -> tuple[Modul, ...]:
        return tuple(self._module)

    @property
    def ziele(self) -> tuple[Studienziel, ...]:
        return tuple(self._ziele)

    def modul(self, kuerzel: str) -> Modul | None:
        return next((m for m in self._module if m.kuerzel == kuerzel), None)

    def semester(self, nummer: int) -> Semester | None:
        return next((s for s in self._semester if s.nummer == nummer), None)

    def semester_von(self, modul: Modul) -> Semester | None:
        """Semester, dem das Modul zugeordnet ist, oder None."""
        return next((s for s in self._semester if any(m is modul for m in s.module)), None)

    def aktuelles_semester(self, stichtag: date) -> Semester | None:
        return next((s for s in self._semester if s.enthaelt(stichtag)), None)

    # ------------------------------------------------------------ Kennzahlen
    def regelstudienzeit(self) -> int:
        """Anzahl der geplanten Semester."""
        return len(self._semester)

    def bestandene_ects(self) -> int:
        return sum(m.ects for m in self._module if m.ist_bestanden())

    def notendurchschnitt(self) -> Decimal | None:
        """ECTS-gewichteter Durchschnitt der bestandenen Module, None ohne Note."""
        benotet = [m for m in self._module if m.ist_bestanden()]
        if not benotet:
            return None
        summe = sum(m.note() * m.ects for m in benotet)
        gewicht = sum(m.ects for m in benotet)
        return (summe / gewicht).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def verstrichene_semester(self, stichtag: date) -> Decimal:
        """Verstrichene Studienzeit in Semestern, tagesgenau anteilig."""
        if stichtag < self._startdatum:
            return Decimal(0)
        nummer = 1
        while self.semesterbeginn(nummer + 1) <= stichtag:
            nummer += 1
        beginn, naechster = self.semesterbeginn(nummer), self.semesterbeginn(nummer + 1)
        anteil = Decimal((stichtag - beginn).days) / Decimal((naechster - beginn).days)
        return Decimal(nummer - 1) + anteil

    def soll_ects(self, stichtag: date) -> Decimal:
        """Einzige Berechnung des Sollwerts: tagesgenau, gedeckelt bei gesamt_ects.

        Der Marker in Bereich C zeigt diesen Wert direkt. Die Ampel des
        Abschlussziels rundet ihn auf volle Module ab (Abschlussziel.abweichung).
        """
        if not self._semester:
            raise ValueError("Ohne Semester lässt sich kein Sollwert berechnen")
        je_semester = Decimal(self._gesamt_ects) / Decimal(self.regelstudienzeit())
        soll = self.verstrichene_semester(stichtag) * je_semester
        return min(soll, Decimal(self._gesamt_ects))
