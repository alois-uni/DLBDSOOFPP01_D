"""Paket domain: Entity-Klassen und alle Regeln, die genau ein Objekt betreffen.

Das Paket importiert keines der anderen Pakete (Phase 2, Abschnitt 2.1).
"""

from domain.aufzaehlungen import Abschlussgrad, Ampel, Pruefungsstatus
from domain.modul import Modul, Semester
from domain.pruefungsleistung import (
    MAX_VERSUCHE, PHASEN_JE_PORTFOLIO, SETZBARE_STATUS, ZULAESSIGE_NOTEN, AdvancedWorkbook, Klausur,
    Portfolio, Pruefungsleistung, SchriftlicheArbeit)
from domain.studiengang import Studiengang
from domain.studienziel import ECTS_JE_MODUL, Abschlussziel, Notenziel, Studienziel

__all__ = [
    "Abschlussgrad", "Ampel", "Pruefungsstatus", "Modul", "Semester",
    "MAX_VERSUCHE", "PHASEN_JE_PORTFOLIO", "SETZBARE_STATUS", "ZULAESSIGE_NOTEN", "AdvancedWorkbook",
    "Klausur", "Portfolio", "Pruefungsleistung", "SchriftlicheArbeit",
    "Studiengang", "ECTS_JE_MODUL", "Abschlussziel", "Notenziel", "Studienziel",
]
