"""Studienziele und ihre Ampel (Bereiche A und B der Skizze).

ampelstatus() ist nur einmal in der Oberklasse umgesetzt und ruft die
abstrakte Methode abweichung() auf. Jedes Ziel misst seine Abweichung in der
Einheit seiner Toleranz: das Abschlussziel in Modulen, das Notenziel in
Notenpunkten. Ein drittes Ziel bräuchte nur eine neue Unterklasse.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from domain.aufzaehlungen import Ampel

if TYPE_CHECKING:                       # nur für Typangaben, vermeidet Zirkelimport
    from domain.studiengang import Studiengang

#: ECTS eines Standardmoduls. Die Ampel zählt nur volle Module, weil ECTS
#: erst mit dem Bestehen eines ganzen Moduls gutgeschrieben werden.
ECTS_JE_MODUL = 5


class Studienziel(ABC):
    def __init__(self, bezeichnung: str, toleranz: Decimal, ist_aktiv: bool = True) -> None:
        if toleranz < 0:
            raise ValueError("Die Toleranz darf nicht negativ sein")
        self._bezeichnung = bezeichnung
        self._toleranz = toleranz
        self._ist_aktiv = ist_aktiv

    @property
    def bezeichnung(self) -> str:
        return self._bezeichnung

    @property
    def toleranz(self) -> Decimal:
        return self._toleranz

    @property
    def ist_aktiv(self) -> bool:
        return self._ist_aktiv

    @abstractmethod
    def abweichung(self, sg: Studiengang, stichtag: date) -> Decimal | None:
        """Rückstand in der Einheit der Toleranz; <= 0 heißt eingehalten.

        None, wenn sich noch nichts sagen lässt (z. B. keine Note).
        """

    def ampelstatus(self, sg: Studiengang, stichtag: date) -> Ampel:
        abweichung = self.abweichung(sg, stichtag)
        if abweichung is None or abweichung <= 0:
            return Ampel.GRUEN
        if abweichung <= self._toleranz:
            return Ampel.GELB
        return Ampel.ROT


class Abschlussziel(Studienziel):
    """Ziel 1: Abschluss in der Regelstudienzeit."""

    def __init__(self, bezeichnung: str, toleranz: Decimal, ziel_semesterzahl: int,
                 ist_aktiv: bool = True) -> None:
        super().__init__(bezeichnung, toleranz, ist_aktiv)
        if ziel_semesterzahl < 1:
            raise ValueError("Die Zielsemesterzahl muss positiv sein")
        self._ziel_semesterzahl = ziel_semesterzahl

    @property
    def ziel_semesterzahl(self) -> int:
        return self._ziel_semesterzahl

    @staticmethod
    def soll_in_modulstufen(soll: Decimal) -> int:
        """Rundet den tagesgenauen Sollwert auf volle Module ab (V1, Phase 2)."""
        module = (soll / ECTS_JE_MODUL).to_integral_value(rounding=ROUND_FLOOR)
        return int(module) * ECTS_JE_MODUL

    def abweichung(self, sg: Studiengang, stichtag: date) -> Decimal:
        """Rückstand in Modulen gegenüber dem abgerundeten Sollwert."""
        soll = self.soll_in_modulstufen(sg.soll_ects(stichtag))
        return Decimal(soll - sg.bestandene_ects()) / ECTS_JE_MODUL

    def prognose_semester(self, sg: Studiengang, stichtag: date) -> Decimal | None:
        """Hochrechnung der Studiendauer beim bisherigen Tempo (Phase 1, Tab. 1)."""
        verstrichen = sg.verstrichene_semester(stichtag)
        bestanden = sg.bestandene_ects()
        if verstrichen <= 0 or bestanden <= 0:
            return None
        tempo = Decimal(bestanden) / verstrichen
        return (Decimal(sg.gesamt_ects) / tempo).quantize(Decimal("0.1"),
                                                          rounding=ROUND_HALF_UP)


class Notenziel(Studienziel):
    """Ziel 2: Notendurchschnitt höchstens ziel_durchschnitt."""

    def __init__(self, bezeichnung: str, toleranz: Decimal, ziel_durchschnitt: Decimal,
                 ist_aktiv: bool = True) -> None:
        super().__init__(bezeichnung, toleranz, ist_aktiv)
        self._ziel_durchschnitt = ziel_durchschnitt

    @property
    def ziel_durchschnitt(self) -> Decimal:
        return self._ziel_durchschnitt

    def abweichung(self, sg: Studiengang, stichtag: date) -> Decimal | None:
        """Abstand des Durchschnitts zum Ziel in Notenpunkten; None ohne Note."""
        durchschnitt = sg.notendurchschnitt()
        if durchschnitt is None:
            return None
        return durchschnitt - self._ziel_durchschnitt

    def restdurchschnitt(self, sg: Studiengang) -> Decimal | None:
        """Durchschnitt, den die noch offenen ECTS erreichen müssen.

        Die eigentliche Steuergröße (Phase 1, Tab. 1). None, wenn keine ECTS
        mehr offen sind.
        """
        bestanden = [m for m in sg.module if m.ist_bestanden()]
        erreicht = sum(m.ects for m in bestanden)
        rest = sg.gesamt_ects - erreicht
        if rest <= 0:
            return None
        summe_ist = sum((m.note() * m.ects for m in bestanden), Decimal(0))
        summe_soll = self._ziel_durchschnitt * sg.gesamt_ects
        return ((summe_soll - summe_ist) / rest).quantize(Decimal("0.01"),
                                                          rounding=ROUND_HALF_UP)
