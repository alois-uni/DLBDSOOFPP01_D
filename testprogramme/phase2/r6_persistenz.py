"""
Reflexionstest 6 - Speichern und Laden der Objektstruktur
=========================================================
Leitfrage: Wie wird aus den flachen Tabellen einer SQLite-Datenbank wieder
die verschachtelte Objektstruktur des Klassendiagramms, mit den richtigen
Unterklassen von Pruefungsleistung?

  1. Rundreise: speichern, Verbindung schliessen, neu laden
  2. Unterklassen ueber eine Spalte "art" (Diskriminator)
  3. Eine unbekannte Art wird schon von der Datenbank abgelehnt
  4. Aggregation: ein Modul bleibt dasselbe Objekt und darf ohne Semester sein
  5. Komposition: Loeschen in der Datenbank nur mit eingeschalteten Fremdschluesseln
  6. Privater Zustand wird ueber den Konstruktor wiederhergestellt und geprueft
  7. Bewertungsdatum bestimmt die Reihenfolge des Notenverlaufs

Ausschliesslich Standardbibliothek. Die Datenbank liegt in einem temporaeren
Verzeichnis und wird am Ende entfernt.
"""

from __future__ import annotations

import sqlite3
import tempfile
from abc import ABC, abstractmethod
from contextlib import closing
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path


def befund(nr: int, text: str) -> None:
    print(f"Befund {nr}: {text}")


# ---------------------------------------------------------------- Domain
ZULAESSIGE_NOTEN = frozenset(Decimal(n) for n in (
    "1.0", "1.3", "1.7", "2.0", "2.3", "2.7", "3.0", "3.3", "3.7", "4.0", "5.0"))


class Pruefungsstatus(Enum):
    GEPLANT = "geplant"
    ANGEMELDET = "angemeldet"
    ABGEGEBEN = "abgegeben"
    BESTANDEN = "bestanden"
    NICHT_BESTANDEN = "nichtBestanden"


class Pruefungsleistung(ABC):
    def __init__(self, *, status: Pruefungsstatus = Pruefungsstatus.GEPLANT,
                 note: Decimal | None = None, bewertet_am: date | None = None) -> None:
        # Der Konstruktor nimmt auch gespeicherten Zustand an und prueft ihn.
        if note is not None and note not in ZULAESSIGE_NOTEN:
            raise ValueError(f"{note} ist keine zulaessige Note")
        self._status = status
        self._note = note
        self._bewertet_am = bewertet_am

    @property
    def status(self) -> Pruefungsstatus:
        return self._status

    @property
    def note(self) -> Decimal | None:
        return self._note

    @property
    def bewertet_am(self) -> date | None:
        return self._bewertet_am

    def note_eintragen(self, note: Decimal, datum: date) -> None:
        if note not in ZULAESSIGE_NOTEN:
            raise ValueError(f"{note} ist keine zulaessige Note")
        self._note = note
        self._bewertet_am = datum
        bestanden = note <= Decimal("4.0")
        self._status = (Pruefungsstatus.BESTANDEN if bestanden
                        else Pruefungsstatus.NICHT_BESTANDEN)

    @abstractmethod
    def naechster_termin(self) -> date | None:
        """Jede Pruefungsform bestimmt ihren Termin selbst."""


class Klausur(Pruefungsleistung):
    def __init__(self, pruefungstermin: date | None, **zustand) -> None:
        super().__init__(**zustand)
        self._pruefungstermin = pruefungstermin

    @property
    def pruefungstermin(self) -> date | None:
        return self._pruefungstermin

    def naechster_termin(self) -> date | None:
        return self._pruefungstermin


class AdvancedWorkbook(Pruefungsleistung):
    def __init__(self, abgabefrist: date, **zustand) -> None:
        super().__init__(**zustand)
        self._abgabefrist = abgabefrist

    @property
    def abgabefrist(self) -> date:
        return self._abgabefrist

    def naechster_termin(self) -> date | None:
        return self._abgabefrist


class Portfolio(Pruefungsleistung):
    def __init__(self, phasenfristen: list[date], abgegebene_phasen: int = 0,
                 **zustand) -> None:
        super().__init__(**zustand)
        if not phasenfristen:
            raise ValueError("Portfolio braucht mindestens eine Phasenfrist [1..*]")
        self._phasenfristen = sorted(phasenfristen)
        self._abgegebene_phasen = abgegebene_phasen

    @property
    def phasenfristen(self) -> tuple[date, ...]:
        return tuple(self._phasenfristen)

    @property
    def abgegebene_phasen(self) -> int:
        return self._abgegebene_phasen

    def phase_abgeben(self) -> None:
        self._abgegebene_phasen += 1

    def naechster_termin(self) -> date | None:
        offen = self._phasenfristen[self._abgegebene_phasen:]
        return offen[0] if offen else None


class Modul:
    def __init__(self, kuerzel: str, bezeichnung: str, ects: int,
                 pruefungsleistung: Pruefungsleistung) -> None:
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


class Semester:
    def __init__(self, nummer: int) -> None:
        self._nummer = nummer
        self._module: list[Modul] = []                   # Aggregation

    @property
    def nummer(self) -> int:
        return self._nummer

    @property
    def module(self) -> tuple[Modul, ...]:
        return tuple(self._module)

    def modul_zuordnen(self, modul: Modul) -> None:
        self._module.append(modul)


class Studiengang:
    def __init__(self, bezeichnung: str, gesamt_ects: int = 180) -> None:
        self._bezeichnung = bezeichnung
        self._gesamt_ects = gesamt_ects
        self._semester: list[Semester] = []              # Komposition
        self._module: list[Modul] = []                   # Komposition (Modulkatalog)

    def neues_semester(self) -> Semester:
        semester = Semester(len(self._semester) + 1)
        self._semester.append(semester)
        return semester

    def neues_modul(self, kuerzel: str, bezeichnung: str, ects: int,
                    pruefungsleistung: Pruefungsleistung) -> Modul:
        modul = Modul(kuerzel, bezeichnung, ects, pruefungsleistung)
        self._module.append(modul)
        return modul

    @property
    def bezeichnung(self) -> str:
        return self._bezeichnung

    @property
    def gesamt_ects(self) -> int:
        return self._gesamt_ects

    @property
    def semester(self) -> tuple[Semester, ...]:
        return tuple(self._semester)

    @property
    def module(self) -> tuple[Modul, ...]:
        return tuple(self._module)

    def modul(self, kuerzel: str) -> Modul | None:
        return next((m for m in self._module if m.kuerzel == kuerzel), None)

    def notenverlauf(self) -> list[Decimal]:
        """Gewichteter Durchschnitt nach jeder Bewertung, in Bewertungsreihenfolge."""
        bewertet = sorted((m for m in self._module if m.pruefungsleistung.note is not None),
                          key=lambda m: m.pruefungsleistung.bewertet_am)
        verlauf, summe, gewicht = [], Decimal(0), 0
        for m in bewertet:
            summe += m.pruefungsleistung.note * m.ects
            gewicht += m.ects
            verlauf.append((summe / gewicht).quantize(Decimal("0.01")))
        return verlauf


# ---------------------------------------------------------------- Repository
SCHEMA = """
CREATE TABLE studiengang (
    id          INTEGER PRIMARY KEY,
    bezeichnung TEXT    NOT NULL,
    gesamt_ects INTEGER NOT NULL
);
CREATE TABLE semester (                       -- Komposition: stirbt mit dem Studiengang
    id             INTEGER PRIMARY KEY,
    studiengang_id INTEGER NOT NULL REFERENCES studiengang(id) ON DELETE CASCADE,
    nummer         INTEGER NOT NULL,
    UNIQUE (studiengang_id, nummer)
);
CREATE TABLE modul (
    id             INTEGER PRIMARY KEY,
    studiengang_id INTEGER NOT NULL REFERENCES studiengang(id) ON DELETE CASCADE,
    semester_id    INTEGER REFERENCES semester(id) ON DELETE SET NULL,   -- Aggregation [0..1]
    kuerzel        TEXT    NOT NULL UNIQUE,
    bezeichnung    TEXT    NOT NULL,
    ects           INTEGER NOT NULL
);
CREATE TABLE pruefungsleistung (              -- eine Tabelle fuer alle Unterklassen
    modul_id          INTEGER PRIMARY KEY REFERENCES modul(id) ON DELETE CASCADE,
    art               TEXT    NOT NULL CHECK (art IN ('klausur', 'advanced_workbook', 'portfolio')),
    status            TEXT    NOT NULL,
    note              TEXT,
    bewertet_am       TEXT,
    termin            TEXT,                   -- Klausur: Pruefungstermin, Workbook: Abgabefrist
    abgegebene_phasen INTEGER                 -- nur Portfolio
);
CREATE TABLE phasenfrist (                    -- Multiplizitaet [1..*] braucht eine eigene Tabelle
    modul_id INTEGER NOT NULL REFERENCES pruefungsleistung(modul_id) ON DELETE CASCADE,
    nr       INTEGER NOT NULL,
    frist    TEXT    NOT NULL,
    PRIMARY KEY (modul_id, nr)
);
"""

ART_VON_KLASSE = {Klausur: "klausur", AdvancedWorkbook: "advanced_workbook",
                  Portfolio: "portfolio"}


def _datum(text: str | None) -> date | None:
    return date.fromisoformat(text) if text else None


class SqliteStudiengangRepository:
    def __init__(self, dateipfad: Path) -> None:
        self._dateipfad = dateipfad

    def _verbinde(self) -> sqlite3.Connection:
        verbindung = sqlite3.connect(self._dateipfad)
        verbindung.execute("PRAGMA foreign_keys = ON")   # in SQLite je Verbindung noetig
        return verbindung

    def erstelle_tabellen(self) -> None:
        with closing(self._verbinde()) as verbindung, verbindung:
            verbindung.executescript(SCHEMA)

    def speichere(self, sg: Studiengang) -> None:
        """Ersetzt den gesamten Bestand in einer Transaktion."""
        with closing(self._verbinde()) as verbindung, verbindung:
            verbindung.execute("DELETE FROM studiengang")           # loescht per CASCADE alles
            verbindung.execute("INSERT INTO studiengang VALUES (1, ?, ?)",
                               (sg.bezeichnung, sg.gesamt_ects))
            semester_id = {}
            for semester in sg.semester:
                cur = verbindung.execute(
                    "INSERT INTO semester (studiengang_id, nummer) VALUES (1, ?)",
                    (semester.nummer,))
                for modul in semester.module:
                    semester_id[modul.kuerzel] = cur.lastrowid
            for modul in sg.module:
                cur = verbindung.execute(
                    "INSERT INTO modul (studiengang_id, semester_id, kuerzel, bezeichnung, ects) "
                    "VALUES (1, ?, ?, ?, ?)",
                    (semester_id.get(modul.kuerzel), modul.kuerzel, modul.bezeichnung, modul.ects))
                self._speichere_leistung(verbindung, cur.lastrowid, modul.pruefungsleistung)

    @staticmethod
    def _speichere_leistung(verbindung: sqlite3.Connection, modul_id: int,
                            pl: Pruefungsleistung) -> None:
        termin, phasen = None, None
        if isinstance(pl, Klausur):
            termin = pl.pruefungstermin
        elif isinstance(pl, AdvancedWorkbook):
            termin = pl.abgabefrist
        elif isinstance(pl, Portfolio):
            phasen = pl.abgegebene_phasen
        verbindung.execute(
            "INSERT INTO pruefungsleistung VALUES (?, ?, ?, ?, ?, ?, ?)",
            (modul_id, ART_VON_KLASSE[type(pl)], pl.status.value,
             str(pl.note) if pl.note is not None else None,
             pl.bewertet_am.isoformat() if pl.bewertet_am else None,
             termin.isoformat() if termin else None, phasen))
        if isinstance(pl, Portfolio):
            verbindung.executemany(
                "INSERT INTO phasenfrist VALUES (?, ?, ?)",
                [(modul_id, nr, frist.isoformat())
                 for nr, frist in enumerate(pl.phasenfristen, start=1)])

    def lade(self) -> Studiengang:
        with closing(self._verbinde()) as verbindung:
            bezeichnung, gesamt_ects = verbindung.execute(
                "SELECT bezeichnung, gesamt_ects FROM studiengang").fetchone()
            sg = Studiengang(bezeichnung, gesamt_ects)

            # 1. Semester in der Reihenfolge ihrer Nummer
            semester_von_id = {}
            for sid, in verbindung.execute("SELECT id FROM semester ORDER BY nummer"):
                semester_von_id[sid] = sg.neues_semester()

            # 2. Phasenfristen je Portfolio einsammeln
            fristen: dict[int, list[date]] = {}
            for modul_id, frist in verbindung.execute(
                    "SELECT modul_id, frist FROM phasenfrist ORDER BY modul_id, nr"):
                fristen.setdefault(modul_id, []).append(date.fromisoformat(frist))

            # 3. Module mit ihrer Pruefungsleistung; die Spalte art waehlt die Unterklasse
            zeilen = verbindung.execute(
                "SELECT m.id, m.semester_id, m.kuerzel, m.bezeichnung, m.ects, p.art, "
                "p.status, p.note, p.bewertet_am, p.termin, p.abgegebene_phasen "
                "FROM modul m JOIN pruefungsleistung p ON p.modul_id = m.id "
                "ORDER BY m.id").fetchall()
            for (modul_id, semester_id, kuerzel, bez, ects, art, status, note,
                 bewertet_am, termin, phasen) in zeilen:
                zustand = dict(status=Pruefungsstatus(status),
                               note=Decimal(note) if note is not None else None,
                               bewertet_am=_datum(bewertet_am))
                if art == "klausur":
                    pl = Klausur(_datum(termin), **zustand)
                elif art == "advanced_workbook":
                    pl = AdvancedWorkbook(_datum(termin), **zustand)
                else:
                    pl = Portfolio(fristen[modul_id], phasen, **zustand)
                modul = sg.neues_modul(kuerzel, bez, ects, pl)
                # 4. Aggregation: dasselbe Modulobjekt dem Semester zuordnen
                if semester_id is not None:
                    semester_von_id[semester_id].modul_zuordnen(modul)
        return sg


# ---------------------------------------------------------------- Hilfen fuer den Test
def abbild(sg: Studiengang) -> tuple:
    """Verschachtelte Darstellung zum Vergleich zweier Objektstrukturen."""
    def leistung(pl: Pruefungsleistung) -> tuple:
        return (type(pl).__name__, pl.status, pl.note, pl.bewertet_am, pl.naechster_termin())
    return (sg.bezeichnung, sg.gesamt_ects,
            tuple((m.kuerzel, m.ects, leistung(m.pruefungsleistung)) for m in sg.module),
            tuple((s.nummer, tuple(m.kuerzel for m in s.module)) for s in sg.semester))


def beispiel() -> Studiengang:
    sg = Studiengang("Cyber Security (B.Sc.)")
    s1 = sg.neues_semester()
    sg.neues_semester()
    mathe = sg.neues_modul("IMT101", "Mathematik Grundlagen I", 5,
                           Klausur(date(2026, 11, 20)))
    oop = sg.neues_modul("DLBDSOOFPP01_D", "Objektorientierte Programmierung", 5,
                         Portfolio([date(2026, 9, 15), date(2026, 10, 27), date(2026, 12, 8)]))
    wiss = sg.neues_modul("DLBWIRITT01", "Einfuehrung in das wiss. Arbeiten", 5,
                          AdvancedWorkbook(date(2026, 10, 5)))
    sg.neues_modul("DLBCSWAHL", "Wahlmodul ohne Semester", 5, Klausur(None))
    for modul in (mathe, oop, wiss):
        s1.modul_zuordnen(modul)
    oop.pruefungsleistung.phase_abgeben()
    # Die Klausur liegt im Plan nach dem Workbook, wird aber zuerst bewertet.
    mathe.pruefungsleistung.note_eintragen(Decimal("1.3"), date(2026, 12, 1))
    wiss.pruefungsleistung.note_eintragen(Decimal("2.3"), date(2026, 12, 18))
    return sg


def anzahl(verbindung: sqlite3.Connection) -> dict[str, int]:
    return {t: verbindung.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("semester", "modul", "pruefungsleistung", "phasenfrist")}


# ---------------------------------------------------------------- Befunde
def main() -> None:
    with tempfile.TemporaryDirectory() as ordner:
        pfad = Path(ordner) / "studium.db"
        repo = SqliteStudiengangRepository(pfad)
        repo.erstelle_tabellen()

        # 1) Rundreise ueber zwei getrennte Verbindungen
        original = beispiel()
        repo.speichere(original)
        geladen = repo.lade()
        assert geladen is not original and abbild(geladen) == abbild(original)
        befund(1, f"Nach Speichern und erneutem Laden stimmt die Struktur ueberein: "
                  f"{len(geladen.semester)} Semester, {len(geladen.module)} Module "
                  "mit je einer Pruefungsleistung.")

        # 2) Unterklassen und Polymorphie nach dem Laden
        arten = {m.kuerzel: type(m.pruefungsleistung) for m in geladen.module}
        assert arten["IMT101"] is Klausur and arten["DLBDSOOFPP01_D"] is Portfolio
        assert arten["DLBWIRITT01"] is AdvancedWorkbook
        termin = geladen.modul("DLBDSOOFPP01_D").pruefungsleistung.naechster_termin()
        assert termin == date(2026, 10, 27)
        befund(2, "Die Spalte art liefert wieder Klausur, Portfolio und AdvancedWorkbook. "
                  f"naechster_termin() des geladenen Portfolios ergibt {termin}, die Frist "
                  "der zweiten Phase, weil die erste als abgegeben gespeichert ist.")

        # 3) Unbekannte Art
        with closing(repo._verbinde()) as verbindung:
            try:
                verbindung.execute("UPDATE pruefungsleistung SET art = 'hausarbeit' "
                                   "WHERE modul_id = 1")
                raise AssertionError("unbekannte Art haette abgelehnt werden sollen")
            except sqlite3.IntegrityError as e:
                befund(3, f"Die Datenbank lehnt die Art 'hausarbeit' ab ({e}). Eine neue "
                          "Pruefungsform braucht damit drei Stellen: Klasse, CHECK und "
                          "Repository.")

        # 4) Aggregation: Identitaet und Modul ohne Semester
        oop = geladen.modul("DLBDSOOFPP01_D")
        assert any(m is oop for m in geladen.semester[0].module)
        wahl = geladen.modul("DLBCSWAHL")
        assert wahl is not None and all(wahl not in s.module for s in geladen.semester)
        befund(4, "Das Modul im Semester ist dasselbe Objekt wie im Modulkatalog, keine "
                  "Kopie. Das Wahlmodul ohne Semester bleibt erhalten, seine Spalte "
                  "semester_id ist NULL.")

        # 5) Komposition in der Datenbank
        with closing(sqlite3.connect(pfad)) as ohne:     # Fremdschluessel nicht eingeschaltet
            ohne.execute("DELETE FROM studiengang")
            verwaist = anzahl(ohne)
            ohne.rollback()
        with closing(repo._verbinde()) as mit:
            mit.execute("DELETE FROM studiengang")
            geloescht = anzahl(mit)
            mit.rollback()
        assert verwaist["modul"] == 4 and all(n == 0 for n in geloescht.values())
        befund(5, f"Ohne PRAGMA foreign_keys bleiben nach dem Loeschen des Studiengangs "
                  f"{verwaist['modul']} Module und {verwaist['phasenfrist']} Phasenfristen "
                  "verwaist zurueck. Mit dem PRAGMA loescht ON DELETE CASCADE alle Teile.")

        # 6) Gespeicherter Zustand wird beim Laden geprueft
        with closing(repo._verbinde()) as verbindung, verbindung:
            verbindung.execute("UPDATE pruefungsleistung SET note = '2.2' WHERE modul_id = 1")
        try:
            repo.lade()
            raise AssertionError("Note 2,2 haette beim Laden auffallen sollen")
        except ValueError as e:
            befund(6, f"Eine von Hand geaenderte Note faellt beim Laden auf ({e}). Das "
                      "Repository liest ueber Properties und uebergibt den Zustand dem "
                      "Konstruktor, es greift auf kein privates Attribut zu.")
        repo.speichere(original)

        # 7) Reihenfolge des Notenverlaufs
        verlauf = repo.lade().notenverlauf()
        assert verlauf == [Decimal("1.30"), Decimal("1.80")]
        befund(7, f"Der Notenverlauf nach Bewertungsdatum lautet {[str(v) for v in verlauf]}. "
                  "Nach den geplanten Terminen staende das Workbook (5.10.) vor der "
                  "Klausur (20.11.), der Verlauf begaenne dann faelschlich mit 2.30.")

    print("\nAlle Pruefungen bestanden.")


if __name__ == "__main__":
    main()
