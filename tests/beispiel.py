"""Testdaten: der Stand der Dashboard-Skizze aus Phase 1 (Stichtag 20.01.2027).

Unabhängig von den CSV-Dateien, damit die Tests nicht von den Beispieldaten
abhängen. Fünf Module des 1. Semesters sind bestanden, Mathematik
Grundlagen I ist angemeldet und selbst zum 05.02.2027 geplant.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from domain import (Abschlussgrad, Abschlussziel, AdvancedWorkbook, Klausur, Notenziel,
                    Portfolio, Pruefungsstatus, SchriftlicheArbeit, Studiengang)

STICHTAG_SKIZZE = date(2027, 1, 20)


def skizze() -> Studiengang:
    sg = Studiengang("Cyber Security", Abschlussgrad.BACHELOR_OF_SCIENCE, date(2026, 8, 10))
    for _ in range(6):
        sg.neues_semester()
    sg.neues_ziel(Abschlussziel("Abschluss in 6 Semestern", Decimal("1"), 6))
    sg.neues_ziel(Notenziel("Notendurchschnitt ≤ 1,9", Decimal("0.1"), Decimal("1.9")))

    def bestanden(note: str, am: date) -> dict:
        return dict(status=Pruefungsstatus.BESTANDEN, note=Decimal(note), bewertet_am=am)

    s1 = sg.semester(1)
    for modul in (
        sg.neues_modul("WISS", "Einführung in das wissenschaftliche Arbeiten", 5,
                       AdvancedWorkbook(date(2026, 8, 30), **bestanden("1.7", date(2026, 9, 20)))),
        sg.neues_modul("PY", "Einführung in die Programmierung mit Python", 5,
                       Klausur(date(2026, 9, 9), **bestanden("2.0", date(2026, 9, 15)))),
        sg.neues_modul("BS", "Betriebssysteme, Rechnernetze und verteilte Systeme", 5,
                       Klausur(date(2026, 9, 28), **bestanden("2.3", date(2026, 10, 2)))),
        sg.neues_modul("OOP", "Objektorientierte u. funktionale Programmierung", 5,
                       Portfolio([date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 30)],
                                 3, **bestanden("1.7", date(2026, 11, 20)))),
        sg.neues_modul("SEC", "Einführung in Datenschutz und IT-Sicherheit", 5,
                       Klausur(date(2026, 10, 9), **bestanden("2.3", date(2026, 10, 9)))),
        sg.neues_modul("MATHE", "Mathematik Grundlagen I", 5,
                       Klausur(None, status=Pruefungsstatus.ANGEMELDET,
                               zieltermin=date(2027, 2, 5))),
    ):
        s1.modul_zuordnen(modul)
    # Katalog ohne Semester: je eine Form, die noch nicht belegt ist
    sg.neues_modul("BA", "Bachelorarbeit", 10, SchriftlicheArbeit())
    sg.neues_modul("SIEM", "Projekt: SIEM-Systeme", 5, Portfolio())
    return sg
