"""SQLite-Repository und Beispieldaten (Muster aus Testprogramm r6)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path

from domain import AdvancedWorkbook, Klausur, Portfolio, SchriftlicheArbeit, Studiengang
from repository import SqliteStudiengangRepository
from tests.beispiel import skizze
from werkzeuge.beispieldatenbank_erzeugen import DATEN, erzeuge_studiengang


def abbild(sg: Studiengang) -> tuple:
    """Verschachtelte Darstellung zum Vergleich zweier Objektstrukturen."""
    def leistung(pl) -> tuple:
        return (type(pl).__name__, pl.bezeichnung, pl.status, pl.versuchsnummer, pl.note,
                pl.bewertet_am, pl.zieltermin, pl.naechster_termin())
    return (sg.bezeichnung, sg.abschluss, sg.startdatum, sg.gesamt_ects,
            tuple((m.kuerzel, m.bezeichnung, m.ects, leistung(m.pruefungsleistung))
                  for m in sg.module),
            tuple((s.nummer, s.beginn, s.ende, tuple(m.kuerzel for m in s.module))
                  for s in sg.semester_liste),
            tuple((type(z).__name__, z.bezeichnung, z.toleranz, z.ist_aktiv) for z in sg.ziele))


class SqliteRepositoryTest(unittest.TestCase):
    def setUp(self):
        self._ordner = tempfile.TemporaryDirectory()
        self.pfad = Path(self._ordner.name) / "test.db"
        self.repo = SqliteStudiengangRepository(self.pfad)
        self.original = skizze()
        self.repo.speichere(self.original)

    def tearDown(self):
        self._ordner.cleanup()      # scheitert unter Windows, wenn eine Verbindung offen ist

    def test_rundreise_stellt_die_struktur_wieder_her(self):
        geladen = self.repo.lade()
        self.assertIsNot(geladen, self.original)
        self.assertEqual(abbild(geladen), abbild(self.original))

    def test_alle_vier_pruefungsformen_kommen_als_unterklasse_zurueck(self):
        geladen = self.repo.lade()
        arten = {m.kuerzel: type(m.pruefungsleistung) for m in geladen.module}
        self.assertIs(arten["PY"], Klausur)
        self.assertIs(arten["WISS"], AdvancedWorkbook)
        self.assertIs(arten["OOP"], Portfolio)
        self.assertIs(arten["BA"], SchriftlicheArbeit)
        self.assertEqual(geladen.modul("SIEM").pruefungsleistung.phasenfristen, ())

    def test_modul_im_semester_ist_dasselbe_objekt_wie_im_katalog(self):
        geladen = self.repo.lade()
        mathe = geladen.modul("MATHE")
        self.assertTrue(any(m is mathe for m in geladen.semester(1).module))

    def test_unbekannte_pruefungsform_lehnt_die_datenbank_ab(self):
        with closing(sqlite3.connect(self.pfad)) as verbindung:
            with self.assertRaises(sqlite3.IntegrityError):
                verbindung.execute("UPDATE pruefungsleistung SET art = 'hausarbeit'")

    def test_von_hand_geaenderte_note_faellt_beim_laden_auf(self):
        with closing(sqlite3.connect(self.pfad)) as verbindung, verbindung:
            verbindung.execute("UPDATE pruefungsleistung SET note = '2.2' WHERE note = '2.0'")
        with self.assertRaises(ValueError):
            self.repo.lade()

    def test_erneutes_speichern_ersetzt_den_bestand(self):
        sg = self.repo.lade()
        sg.modul("MATHE").pruefungsleistung.note_eintragen(Decimal("1.0"), date(2027, 2, 5))
        self.repo.speichere(sg)
        geladen = self.repo.lade()
        self.assertEqual(geladen.bestandene_ects(), 30)
        self.assertEqual(len(geladen.module), len(sg.module))

    def test_fehlende_datei_wird_gemeldet(self):
        with self.assertRaises(FileNotFoundError):
            SqliteStudiengangRepository(Path(self._ordner.name) / "fehlt.db").lade()


class BeispieldatenTest(unittest.TestCase):
    def test_stammdaten_ergeben_180_ects_im_pflicht_und_wahlbereich(self):
        sg = erzeuge_studiengang(DATEN / "module.csv", DATEN / "stand.csv")
        self.assertEqual(len(sg.module), 62)
        pflicht = sum(m.ects for m in sg.module if m.kuerzel.startswith("P"))
        self.assertEqual(pflicht + 10 + 10 + 30, 180)        # Wahlpflicht A, B, C
        self.assertEqual(sg.bestandene_ects(), 15)
        self.assertEqual(len(sg.semester(1).module), 5)

    def test_mitgelieferte_beispieldatenbank_passt_zu_den_stammdaten(self):
        aus_csv = erzeuge_studiengang(DATEN / "module.csv", DATEN / "stand.csv")
        aus_db = SqliteStudiengangRepository(DATEN / "beispiel.db").lade()
        self.assertEqual(abbild(aus_db), abbild(aus_csv))


if __name__ == "__main__":
    unittest.main()
