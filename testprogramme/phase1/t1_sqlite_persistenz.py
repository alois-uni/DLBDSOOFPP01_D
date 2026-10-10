"""
Machbarkeitstest 1 - Datenhaltung in einer SQLite-Datenbank
===========================================================
Leitfrage aus der Aufgabenstellung:
    "Soll die Datenspeicherung in Dateien oder in einer Datenbank erfolgen?"

Ziel des Tests
--------------
Nachweisen, dass sich die Entity-Struktur des Klassendiagramms
(Studiengang -> Semester -> Modul -> Pruefungsleistung) ohne jede
Fremdbibliothek dauerhaft speichern, wieder einlesen und per SQL
auswerten laesst.

Der Test ist bewusst so aufgebaut, dass er zweimal laeuft:
    1. Durchlauf: Datenbank anlegen und befuellen
    2. Durchlauf: nur lesen - beweist, dass die Daten den
       Programmende ueberdauert haben (Persistenz).

Es wird ausschliesslich die Python-Standardbibliothek verwendet
(sqlite3, pathlib, decimal). Damit ist keine Installation eines
Datenbankservers und kein Administratorrecht noetig.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

DB_PFAD = Path(__file__).with_name("machbarkeit_test.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS studiengang (
    id                INTEGER PRIMARY KEY,
    bezeichnung       TEXT    NOT NULL,
    gesamt_ects       INTEGER NOT NULL,
    regelstudienzeit  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS semester (
    id             INTEGER PRIMARY KEY,
    studiengang_id INTEGER NOT NULL REFERENCES studiengang(id) ON DELETE CASCADE,
    nummer         INTEGER NOT NULL,
    UNIQUE (studiengang_id, nummer)
);

CREATE TABLE IF NOT EXISTS modul (
    id          INTEGER PRIMARY KEY,
    semester_id INTEGER NOT NULL REFERENCES semester(id) ON DELETE CASCADE,
    kuerzel     TEXT    NOT NULL UNIQUE,
    bezeichnung TEXT    NOT NULL,
    ects        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pruefungsleistung (
    id       INTEGER PRIMARY KEY,
    modul_id INTEGER NOT NULL REFERENCES modul(id) ON DELETE CASCADE,
    art      TEXT    NOT NULL,            -- Diskriminator der Vererbungshierarchie
    status   TEXT    NOT NULL,            -- offen | abgegeben | bestanden
    note     TEXT                         -- TEXT, damit Decimal exakt bleibt
);
"""

# (kuerzel, bezeichnung, ects, art, status, note)
TESTDATEN = [
    ("DLBWIRPI01", "Einfuehrung in das wissenschaftliche Arbeiten", 5,
     "SchriftlicheAusarbeitung", "abgegeben", None),
    ("DLBDSIPWP01", "Einfuehrung in die Programmierung mit Python", 5,
     "SchriftlicheAusarbeitung", "abgegeben", None),
    ("IOBP01", "Betriebssysteme, Rechnernetze und verteilte Systeme", 5,
     "Klausur", "offen", None),
    ("DLBDSOOFPP01", "Objektorientierte und funktionale Programmierung", 5,
     "Portfolio", "offen", None),
    ("DEMO01", "Demomodul (nur zum Test der Notenrechnung)", 5,
     "Klausur", "bestanden", "1.7"),
]


def datenbank_aufbauen(verbindung: sqlite3.Connection) -> None:
    """Legt das Schema an. IF NOT EXISTS macht den Aufruf wiederholbar."""
    verbindung.executescript(SCHEMA)


def testdaten_schreiben(verbindung: sqlite3.Connection) -> None:
    """Schreibt einen Studiengang mit einem Semester und fuenf Modulen."""
    cur = verbindung.cursor()
    cur.execute(
        "INSERT INTO studiengang (id, bezeichnung, gesamt_ects, regelstudienzeit) "
        "VALUES (1, 'Cyber Security (B.Sc.)', 180, 6)"
    )
    cur.execute("INSERT INTO semester (id, studiengang_id, nummer) VALUES (1, 1, 1)")
    for kuerzel, bezeichnung, ects, art, status, note in TESTDATEN:
        cur.execute(
            "INSERT INTO modul (semester_id, kuerzel, bezeichnung, ects) "
            "VALUES (1, ?, ?, ?)",
            (kuerzel, bezeichnung, ects),
        )
        cur.execute(
            "INSERT INTO pruefungsleistung (modul_id, art, status, note) "
            "VALUES (?, ?, ?, ?)",
            (cur.lastrowid, art, status, note),
        )
    verbindung.commit()


def kennzahlen_lesen(verbindung: sqlite3.Connection) -> dict[str, object]:
    """
    Liest die beiden Kernkennzahlen des Dashboards direkt per SQL.

    Damit wird geprueft, ob die Datenbank nicht nur speichern, sondern die
    Aggregation auch selbst uebernehmen kann - ein Vorteil gegenueber einer
    reinen Datei-Loesung.
    """
    cur = verbindung.cursor()

    cur.execute(
        "SELECT COALESCE(SUM(m.ects), 0) FROM modul m "
        "JOIN pruefungsleistung p ON p.modul_id = m.id "
        "WHERE p.status = 'bestanden'"
    )
    bestandene_ects = cur.fetchone()[0]

    cur.execute(
        "SELECT p.note, m.ects FROM modul m "
        "JOIN pruefungsleistung p ON p.modul_id = m.id "
        "WHERE p.note IS NOT NULL"
    )
    zeilen = cur.fetchall()

    # Decimal statt float: Noten sind exakte Dezimalwerte in 0,1-Schritten.
    summe = sum(Decimal(note) * ects for note, ects in zeilen)
    gewicht = sum(ects for _, ects in zeilen)
    schnitt = (summe / gewicht) if gewicht else None

    cur.execute("SELECT COUNT(*) FROM pruefungsleistung WHERE status = 'abgegeben'")
    offene_bewertungen = cur.fetchone()[0]

    return {
        "bestandene_ects": bestandene_ects,
        "notendurchschnitt": schnitt,
        "wartet_auf_bewertung": offene_bewertungen,
    }


def main() -> None:
    erstlauf = not DB_PFAD.exists()

    with sqlite3.connect(DB_PFAD) as verbindung:
        datenbank_aufbauen(verbindung)
        if erstlauf:
            testdaten_schreiben(verbindung)
            print(f"Datenbank neu angelegt unter: {DB_PFAD.name}")
        else:
            print(f"Bestehende Datenbank gelesen: {DB_PFAD.name}")
            print("-> Die Daten haben das Programmende ueberdauert (Persistenz).")

        kennzahlen = kennzahlen_lesen(verbindung)

    print()
    print("Ausgelesene Kennzahlen")
    print("----------------------")
    print(f"  Bestandene ECTS        : {kennzahlen['bestandene_ects']} von 180")
    print(f"  Notendurchschnitt      : {kennzahlen['notendurchschnitt']}")
    print(f"  Wartet auf Bewertung   : {kennzahlen['wartet_auf_bewertung']} Leistung(en)")
    print()
    print("Ergebnis: Speichern, Wiedereinlesen und Aggregieren funktionieren")
    print("          allein mit der Standardbibliothek (Modul sqlite3).")
    print("Hinweis:  Zum Wiederholen des Erstlaufs die Datei "
          f"{DB_PFAD.name} loeschen.")


if __name__ == "__main__":
    main()
