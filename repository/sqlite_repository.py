"""Datenhaltung in SQLite nach dem Muster aus Testprogramm r6.

* eine Tabelle je Klasse für Studiengang, Semester und Modul; jede Beziehung
  ein Fremdschlüssel, bei Kompositionen mit ON DELETE CASCADE
* die Aggregation Modul-Semester als Spalte, die leer sein darf
* alle Prüfungsformen in einer Tabelle, die Spalte art wählt beim Laden die
  Unterklasse; eine CHECK-Bedingung lässt nur bekannte Werte zu
* Phasenfristen in eigener Tabelle (Multiplizität [0..*])
* Studienziele ebenso über eine Spalte art
* Fremdschlüssel werden je Verbindung eingeschaltet (PRAGMA foreign_keys)
* Laden über die Konstruktoren, die den gespeicherten Zustand prüfen;
  Speichern liest ausschließlich über Properties
* Verbindungen werden immer geschlossen, weil Windows offene Dateien sperrt

Umwandlungen an der Grenze (r4): Enum <-> Text, Decimal <-> Text,
date <-> ISO-Text.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

from domain import (Abschlussgrad, Abschlussziel, AdvancedWorkbook, Klausur, Notenziel,
                    Portfolio, Pruefungsleistung, Pruefungsstatus, SchriftlicheArbeit,
                    Studiengang, Studienziel)
from repository.studiengang_repository import StudiengangRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS studiengang (
    id          INTEGER PRIMARY KEY,
    bezeichnung TEXT    NOT NULL,
    abschluss   TEXT    NOT NULL,
    startdatum  TEXT    NOT NULL,
    gesamt_ects INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS semester (           -- Komposition
    id             INTEGER PRIMARY KEY,
    studiengang_id INTEGER NOT NULL REFERENCES studiengang(id) ON DELETE CASCADE,
    nummer         INTEGER NOT NULL,
    beginn         TEXT    NOT NULL,
    ende           TEXT    NOT NULL,
    UNIQUE (studiengang_id, nummer)
);
CREATE TABLE IF NOT EXISTS modul (              -- Komposition (Modulkatalog)
    id             INTEGER PRIMARY KEY,
    studiengang_id INTEGER NOT NULL REFERENCES studiengang(id) ON DELETE CASCADE,
    semester_id    INTEGER REFERENCES semester(id) ON DELETE SET NULL,  -- Aggregation [0..1]
    kuerzel        TEXT    NOT NULL UNIQUE,
    bezeichnung    TEXT    NOT NULL,
    ects           INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS pruefungsleistung (  -- eine Tabelle für alle Prüfungsformen
    modul_id          INTEGER PRIMARY KEY REFERENCES modul(id) ON DELETE CASCADE,
    art               TEXT    NOT NULL CHECK (art IN
                          ('klausur', 'advanced_workbook', 'portfolio', 'schriftliche_arbeit')),
    bezeichnung       TEXT    NOT NULL,
    status            TEXT    NOT NULL,
    versuchsnummer    INTEGER NOT NULL,
    note              TEXT,
    bewertet_am       TEXT,
    zieltermin        TEXT,
    termin            TEXT,     -- Klausur: Prüfungstermin, sonst Abgabefrist
    abgegebene_phasen INTEGER   -- nur Portfolio
);
CREATE TABLE IF NOT EXISTS phasenfrist (        -- Multiplizität [0..*]
    modul_id INTEGER NOT NULL REFERENCES pruefungsleistung(modul_id) ON DELETE CASCADE,
    nr       INTEGER NOT NULL,
    frist    TEXT    NOT NULL,
    PRIMARY KEY (modul_id, nr)
);
CREATE TABLE IF NOT EXISTS studienziel (        -- Komposition
    id                INTEGER PRIMARY KEY,
    studiengang_id    INTEGER NOT NULL REFERENCES studiengang(id) ON DELETE CASCADE,
    art               TEXT    NOT NULL CHECK (art IN ('abschluss', 'note')),
    bezeichnung       TEXT    NOT NULL,
    ist_aktiv         INTEGER NOT NULL,
    toleranz          TEXT    NOT NULL,
    ziel_semesterzahl INTEGER,  -- nur Abschlussziel
    ziel_durchschnitt TEXT      -- nur Notenziel
);
"""


def _text(wert: date | Decimal | None) -> str | None:
    if wert is None:
        return None
    return wert.isoformat() if isinstance(wert, date) else str(wert)


def _datum(text: str | None) -> date | None:
    return date.fromisoformat(text) if text else None


def _dezimal(text: str | None) -> Decimal | None:
    return Decimal(text) if text is not None else None


class SqliteStudiengangRepository(StudiengangRepository):
    def __init__(self, dateipfad: Path) -> None:
        self._dateipfad = Path(dateipfad)

    @property
    def dateipfad(self) -> Path:
        return self._dateipfad

    # ------------------------------------------------------------ Verbindung
    def _verbinde(self) -> sqlite3.Connection:
        verbindung = sqlite3.connect(self._dateipfad)
        verbindung.execute("PRAGMA foreign_keys = ON")   # in SQLite je Verbindung nötig
        return verbindung

    def _erstelle_tabellen(self, verbindung: sqlite3.Connection) -> None:
        verbindung.executescript(SCHEMA)

    # ------------------------------------------------------------ Speichern
    def speichere(self, sg: Studiengang) -> None:
        """Ersetzt den gesamten Bestand in einer Transaktion.

        Scheitert ein Schritt, rollt der Kontextmanager der Verbindung alles
        zurück; in der Datei bleibt dann der vorherige Stand.
        """
        with closing(self._verbinde()) as verbindung:
            self._erstelle_tabellen(verbindung)
            with verbindung:
                verbindung.execute("DELETE FROM studiengang")      # CASCADE löscht alle Teile
                verbindung.execute(
                    "INSERT INTO studiengang VALUES (1, ?, ?, ?, ?)",
                    (sg.bezeichnung, sg.abschluss.value, _text(sg.startdatum),
                     sg.gesamt_ects))
                semester_id = {}
                for semester in sg.semester_liste:
                    cur = verbindung.execute(
                        "INSERT INTO semester (studiengang_id, nummer, beginn, ende) "
                        "VALUES (1, ?, ?, ?)",
                        (semester.nummer, _text(semester.beginn), _text(semester.ende)))
                    for modul in semester.module:
                        semester_id[modul.kuerzel] = cur.lastrowid
                for modul in sg.module:
                    cur = verbindung.execute(
                        "INSERT INTO modul (studiengang_id, semester_id, kuerzel, "
                        "bezeichnung, ects) VALUES (1, ?, ?, ?, ?)",
                        (semester_id.get(modul.kuerzel), modul.kuerzel,
                         modul.bezeichnung, modul.ects))
                    self._speichere_leistung(verbindung, cur.lastrowid,
                                             modul.pruefungsleistung)
                for ziel in sg.ziele:
                    self._speichere_ziel(verbindung, ziel)

    @staticmethod
    def _speichere_leistung(verbindung: sqlite3.Connection, modul_id: int,
                            pl: Pruefungsleistung) -> None:
        # Nur hier und in _leistung_aus_zeile wird nach der Prüfungsform gefragt.
        termin, phasen = None, None
        if isinstance(pl, Klausur):
            art, termin = "klausur", pl.pruefungstermin
        elif isinstance(pl, AdvancedWorkbook):
            art, termin = "advanced_workbook", pl.abgabefrist
        elif isinstance(pl, SchriftlicheArbeit):
            art, termin = "schriftliche_arbeit", pl.abgabefrist
        elif isinstance(pl, Portfolio):
            art, phasen = "portfolio", pl.abgegebene_phasen
        else:
            raise TypeError(f"Unbekannte Prüfungsform {type(pl).__name__}")
        verbindung.execute(
            "INSERT INTO pruefungsleistung VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (modul_id, art, pl.bezeichnung, pl.status.value, pl.versuchsnummer,
             _text(pl.note), _text(pl.bewertet_am), _text(pl.zieltermin),
             _text(termin), phasen))
        if isinstance(pl, Portfolio):
            verbindung.executemany(
                "INSERT INTO phasenfrist VALUES (?, ?, ?)",
                [(modul_id, nr, _text(frist))
                 for nr, frist in enumerate(pl.phasenfristen, start=1)])

    @staticmethod
    def _speichere_ziel(verbindung: sqlite3.Connection, ziel: Studienziel) -> None:
        semesterzahl, durchschnitt = None, None
        if isinstance(ziel, Abschlussziel):
            art, semesterzahl = "abschluss", ziel.ziel_semesterzahl
        elif isinstance(ziel, Notenziel):
            art, durchschnitt = "note", _text(ziel.ziel_durchschnitt)
        else:
            raise TypeError(f"Unbekanntes Studienziel {type(ziel).__name__}")
        verbindung.execute(
            "INSERT INTO studienziel (studiengang_id, art, bezeichnung, ist_aktiv, "
            "toleranz, ziel_semesterzahl, ziel_durchschnitt) VALUES (1, ?, ?, ?, ?, ?, ?)",
            (art, ziel.bezeichnung, int(ziel.ist_aktiv), _text(ziel.toleranz),
             semesterzahl, durchschnitt))

    # ------------------------------------------------------------ Laden
    def lade(self) -> Studiengang:
        if not self._dateipfad.exists():
            raise FileNotFoundError(f"Datenbank {self._dateipfad} fehlt")
        with closing(self._verbinde()) as verbindung:
            zeile = verbindung.execute(
                "SELECT bezeichnung, abschluss, startdatum, gesamt_ects "
                "FROM studiengang").fetchone()
            if zeile is None:
                raise LookupError(f"In {self._dateipfad} ist kein Studiengang gespeichert")
            bezeichnung, abschluss, startdatum, gesamt_ects = zeile
            sg = Studiengang(bezeichnung, Abschlussgrad(abschluss),
                             date.fromisoformat(startdatum), gesamt_ects)

            # 1. Semester in der Reihenfolge ihrer Nummer
            semester_von_id = {}
            for sid, beginn, ende in verbindung.execute(
                    "SELECT id, beginn, ende FROM semester ORDER BY nummer"):
                semester_von_id[sid] = sg.neues_semester(date.fromisoformat(beginn),
                                                         date.fromisoformat(ende))

            # 2. Phasenfristen je Portfolio einsammeln
            fristen: dict[int, list[date]] = {}
            for modul_id, frist in verbindung.execute(
                    "SELECT modul_id, frist FROM phasenfrist ORDER BY modul_id, nr"):
                fristen.setdefault(modul_id, []).append(date.fromisoformat(frist))

            # 3. Module mit ihrer Prüfungsleistung
            zeilen = verbindung.execute(
                "SELECT m.id, m.semester_id, m.kuerzel, m.bezeichnung, m.ects, p.art, "
                "p.bezeichnung, p.status, p.versuchsnummer, p.note, p.bewertet_am, "
                "p.zieltermin, p.termin, p.abgegebene_phasen "
                "FROM modul m JOIN pruefungsleistung p ON p.modul_id = m.id "
                "ORDER BY m.id").fetchall()
            for (modul_id, semester_id, kuerzel, modulname, ects, art, *leistung) in zeilen:
                pl = self._leistung_aus_zeile(art, leistung, fristen.get(modul_id, []))
                modul = sg.neues_modul(kuerzel, modulname, ects, pl)
                # 4. Aggregation: dasselbe Modulobjekt dem Semester zuordnen
                if semester_id is not None:
                    semester_von_id[semester_id].modul_zuordnen(modul)

            # 5. Studienziele
            for (art, name, aktiv, toleranz, semesterzahl, durchschnitt) in verbindung.execute(
                    "SELECT art, bezeichnung, ist_aktiv, toleranz, ziel_semesterzahl, "
                    "ziel_durchschnitt FROM studienziel ORDER BY id"):
                if art == "abschluss":
                    ziel = Abschlussziel(name, Decimal(toleranz), semesterzahl, bool(aktiv))
                else:
                    ziel = Notenziel(name, Decimal(toleranz), Decimal(durchschnitt), bool(aktiv))
                sg.neues_ziel(ziel)
        return sg

    @staticmethod
    def _leistung_aus_zeile(art: str, werte: list, fristen: list[date]) -> Pruefungsleistung:
        bezeichnung, status, versuch, note, bewertet_am, zieltermin, termin, phasen = werte
        zustand = dict(bezeichnung=bezeichnung, status=Pruefungsstatus(status),
                       versuchsnummer=versuch, note=_dezimal(note),
                       bewertet_am=_datum(bewertet_am), zieltermin=_datum(zieltermin))
        if art == "klausur":
            return Klausur(_datum(termin), **zustand)
        if art == "advanced_workbook":
            return AdvancedWorkbook(_datum(termin), **zustand)
        if art == "schriftliche_arbeit":
            return SchriftlicheArbeit(_datum(termin), **zustand)
        return Portfolio(fristen, phasen or 0, **zustand)
