"""Erzeugt daten/beispiel.db aus den Stammdaten in daten/module.csv und daten/stand.csv.

Aufruf aus dem Programmordner:   py werkzeuge/beispieldatenbank_erzeugen.py

module.csv  enthält den Modulkatalog: Kürzel, Bezeichnung, ECTS, Prüfungsform
            (klausur, advanced_workbook, portfolio, schriftliche_arbeit),
            Plansemester laut Studienablaufplan (leer bei Wahlpflichtmodulen),
            Termine (Klausur: Prüfungstermin, sonst Abgabefrist, beim Portfolio
            die Phasenfristen durch Leerzeichen getrennt) und Zieltermin.
            Die Prüfungsform steht erst nach der Einschreibung fest; bis dahin
            gilt Klausur, wenn der Titel nichts anderes sagt. Wer sie kennt,
            ändert sie hier und erzeugt die Datenbank neu.
stand.csv   enthält den Fortschritt der belegten Module: Semester (nur nötig,
            wenn es vom Plansemester abweicht), Status, Versuch, Note,
            Bewertungsdatum, abgegebene Phasen.

Alle Werte laufen durch die Konstruktoren und Methoden der Entity-Klassen und
werden dabei geprüft; eine unzulässige Note bricht die Erzeugung ab. Die
Datei daten/studium.db, in der das Dashboard speichert, bleibt unberührt.
Wer mit den neuen Beispieldaten starten will, löscht sie.
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

PROGRAMMORDNER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROGRAMMORDNER))          # Pakete auch beim direkten Aufruf finden

from domain import (Abschlussgrad, Abschlussziel, AdvancedWorkbook, Klausur,  # noqa: E402
                    Notenziel, Portfolio, Pruefungsleistung, Pruefungsstatus,
                    SchriftlicheArbeit, Studiengang)
from repository import SqliteStudiengangRepository  # noqa: E402

DATEN = PROGRAMMORDNER / "daten"

# Stammdaten des Studiengangs (myCampus)
STUDIENGANG = "Cyber Security"
ABSCHLUSS = Abschlussgrad.BACHELOR_OF_SCIENCE
STUDIENBEGINN = date(2026, 8, 10)
GESAMT_ECTS = 180
REGELSTUDIENZEIT = 6

# Spalte pruefungsform -> Konstruktor der passenden Unterklasse
FORMEN = {
    "klausur": lambda termine, zustand: Klausur(termine[0] if termine else None, **zustand),
    "advanced_workbook": lambda termine, zustand: AdvancedWorkbook(
        termine[0] if termine else None, **zustand),
    "schriftliche_arbeit": lambda termine, zustand: SchriftlicheArbeit(
        termine[0] if termine else None, **zustand),
    "portfolio": lambda termine, zustand: Portfolio(
        termine, zustand.pop("abgegebene_phasen"), **zustand),
}


def _lies(datei: Path) -> list[dict[str, str]]:
    """Liest eine CSV-Datei mit Semikolon; utf-8-sig verträgt auch Dateien aus Excel."""
    with datei.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _datum(text: str) -> date | None:
    """ISO-Datum aus der CSV-Datei; leeres Feld wird None."""
    return date.fromisoformat(text) if text.strip() else None


def erzeuge_studiengang(module_csv: Path, stand_csv: Path) -> Studiengang:
    """Baut den Studiengang mit Semestern, Zielen und allen Modulen aus den CSV-Dateien.

    Toleranz der Ziele: Ein Modul Rückstand bzw. ein Durchschnitt bis 0,1
    über der Zielnote gelten noch als gelb.
    """
    sg = Studiengang(STUDIENGANG, ABSCHLUSS, STUDIENBEGINN, GESAMT_ECTS)
    for _ in range(REGELSTUDIENZEIT):
        sg.neues_semester()
    sg.neues_ziel(Abschlussziel(f"Abschluss in {REGELSTUDIENZEIT} Semestern",
                                toleranz=Decimal("1"), ziel_semesterzahl=REGELSTUDIENZEIT))
    sg.neues_ziel(Notenziel("Notendurchschnitt ≤ 1,9", toleranz=Decimal("0.1"),
                            ziel_durchschnitt=Decimal("1.9")))

    stand = {zeile["kuerzel"]: zeile for zeile in _lies(stand_csv)}
    for zeile in _lies(module_csv):
        kuerzel = zeile["kuerzel"].strip()
        fortschritt = stand.pop(kuerzel, None)
        zustand: dict = {"zieltermin": _datum(zeile["zieltermin"]), "abgegebene_phasen": 0}
        if fortschritt:
            zustand.update(
                status=Pruefungsstatus(fortschritt["status"].strip()),
                versuchsnummer=int(fortschritt["versuch"] or 1),
                note=Decimal(fortschritt["note"]) if fortschritt["note"].strip() else None,
                bewertet_am=_datum(fortschritt["bewertet_am"]),
                abgegebene_phasen=int(fortschritt["abgegebene_phasen"] or 0))
        form = zeile["pruefungsform"].strip()
        if form not in FORMEN:
            raise ValueError(f"{kuerzel}: unbekannte Prüfungsform {form!r}")
        if form != "portfolio":
            zustand.pop("abgegebene_phasen")
        termine = [date.fromisoformat(t) for t in zeile["termine"].split()]
        pl: Pruefungsleistung = FORMEN[form](termine, zustand)
        modul = sg.neues_modul(kuerzel, zeile["bezeichnung"].strip(), int(zeile["ects"]), pl)
        nummer = zeile["plansemester"].strip()
        if fortschritt and fortschritt["semester"].strip():
            nummer = fortschritt["semester"].strip()
        if nummer:
            semester = sg.semester(int(nummer))
            if semester is None:
                raise ValueError(f"{kuerzel}: Semester {nummer} gibt es nicht")
            semester.modul_zuordnen(modul)
    if stand:
        raise ValueError(f"stand.csv nennt unbekannte Module: {', '.join(stand)}")
    return sg


def main() -> None:
    """Schreibt daten/beispiel.db neu; eine vorhandene Datei wird ersetzt."""
    sg = erzeuge_studiengang(DATEN / "module.csv", DATEN / "stand.csv")
    ziel = DATEN / "beispiel.db"
    SqliteStudiengangRepository(ziel).speichere(sg)
    print(f"{ziel.name} erzeugt: {len(sg.module)} Module, "
          f"{sum(len(s.module) for s in sg.semester_liste)} davon einem Semester zugeordnet.")


if __name__ == "__main__":
    main()
