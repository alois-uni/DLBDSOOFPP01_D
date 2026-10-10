"""Services und Controller mit InMemoryStudiengangRepository und festem Stichtag."""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from controller import DashboardController
from domain import Ampel, Klausur, Pruefungsstatus
from repository import InMemoryStudiengangRepository
from service import ErfassungsService, KennzahlenService
from tests.beispiel import STICHTAG_SKIZZE, skizze


def controller(stichtag: date = STICHTAG_SKIZZE):
    repository = InMemoryStudiengangRepository(skizze())
    return (DashboardController(repository, KennzahlenService(), ErfassungsService(), stichtag),
            repository)


class KennzahlenTest(unittest.TestCase):
    def setUp(self):
        self.sg = skizze()
        self.service = KennzahlenService()

    def test_laufende_ects_und_ects_je_semester(self):
        self.assertEqual(self.service.laufende_ects(self.sg), 5)
        self.assertEqual(self.service.ects_je_semester(self.sg)[0], (25, 5, 0))
        self.assertEqual(self.service.ects_je_semester(self.sg)[1], (0, 0, 0))
        self.sg.semester(2).modul_zuordnen(self.sg.modul("SIEM"))     # geplant
        self.assertEqual(self.service.ects_je_semester(self.sg)[1], (0, 0, 5))

    def test_notenverlauf_folgt_dem_bewertungsdatum(self):
        # Bewertungsreihenfolge: PY 2,0 / WISS 1,7 / BS 2,3 / SEC 2,3 / OOP 1,7
        self.assertEqual(self.service.notenverlauf(self.sg),
                         [Decimal(w) for w in ("2.00", "1.85", "2.00", "2.08", "2.00")])

    def test_regel_termin_innerhalb_von_30_tagen_mit_zieltermin(self):
        # Wortlaut der Skizze aus Phase 1, Bereich G
        hinweis = self.service.handlungshinweis(self.sg, STICHTAG_SKIZZE)
        self.assertEqual(hinweis, "«Mathematik Grundlagen I»: Klausur schreiben, selbst "
                                  "geplant zum 05.02.2027 (noch 16 Tage), Termin noch "
                                  "nicht gebucht.")

    def test_regel_gebuchter_termin_am_tag_des_zieltermins(self):
        self.sg.modul("MATHE").pruefungsleistung.termin_setzen(date(2027, 2, 5))
        hinweis = self.service.handlungshinweis(self.sg, STICHTAG_SKIZZE)
        self.assertEqual(hinweis, "«Mathematik Grundlagen I»: Klausur schreiben bis "
                                  "05.02.2027 (noch 16 Tage).")

    def test_regel_ueberschrittene_frist_hat_vorrang(self):
        hinweis = self.service.handlungshinweis(self.sg, date(2027, 2, 6))
        self.assertTrue(hinweis.startswith("Frist überschritten: «Mathematik Grundlagen I»"))

    def test_regel_rotes_ziel(self):
        self.sg.modul("MATHE").pruefungsleistung.note_eintragen(Decimal("1.0"), date(2027, 2, 5))
        hinweis = self.service.handlungshinweis(self.sg, date(2027, 6, 1))
        self.assertEqual(hinweis, "Ziel «Abschluss in 6 Semestern» ist rot. "
                                  "Studienplanung prüfen.")

    def test_regel_gelbes_ziel_und_nichts_steht_an(self):
        self.sg.modul("MATHE").pruefungsleistung.note_eintragen(Decimal("2.0"), date(2027, 1, 20))
        self.assertTrue(self.service.handlungshinweis(self.sg, STICHTAG_SKIZZE)
                        .startswith("Ziel «Notendurchschnitt ≤ 1,9» ist gelb"))
        gut = skizze()
        gut.modul("MATHE").pruefungsleistung.note_eintragen(Decimal("1.0"), date(2027, 1, 20))
        self.assertEqual(self.service.handlungshinweis(gut, STICHTAG_SKIZZE),
                         "Derzeit steht nichts an.")


class ErfassungsServiceTest(unittest.TestCase):
    def test_modul_verschieben_und_entfernen(self):
        sg, service = skizze(), ErfassungsService()
        mathe = sg.modul("MATHE")
        service.modul_zuordnen(sg, mathe, 2)
        self.assertIs(sg.semester_von(mathe), sg.semester(2))
        self.assertNotIn(mathe, sg.semester(1).module)
        service.modul_zuordnen(sg, mathe, 0)
        self.assertIsNone(sg.semester_von(mathe))
        self.assertIs(sg.modul("MATHE"), mathe)          # bleibt im Katalog

    def test_unbekanntes_semester_aendert_nichts(self):
        sg, service = skizze(), ErfassungsService()
        with self.assertRaises(ValueError):
            service.modul_zuordnen(sg, sg.modul("MATHE"), 9)
        self.assertIs(sg.semester_von(sg.modul("MATHE")), sg.semester(1))


class ControllerTest(unittest.TestCase):
    def test_dashboard_daten_entsprechen_der_skizze(self):
        c, _ = controller()
        daten = c.dashboard_daten()
        self.assertEqual(daten.kopfzeile, "Cyber Security (B.Sc.) · 1. Semester")
        ziel1, ziel2 = daten.ziele
        self.assertIs(ziel1.ampel, Ampel.GRUEN)
        self.assertEqual(ziel1.aussage, "auf Kurs · 25 ECTS · bis 09.02.2027: 30 ECTS")
        self.assertIs(ziel2.ampel, Ampel.GELB)
        self.assertEqual(ziel2.wert, "Ø 2,00")
        self.assertEqual(ziel2.aussage, "Rest darf im Schnitt 1,88 sein")
        self.assertEqual((daten.ects_bestanden, daten.ects_laufend), (25, 5))
        self.assertAlmostEqual(float(daten.ects_soll_heute), 26.58, places=2)
        self.assertEqual(len(daten.module), 6)
        self.assertEqual(daten.ects_soll_je_semester, 30)

    def test_dto_ist_unveraenderlich(self):
        c, _ = controller()
        daten = c.dashboard_daten()
        with self.assertRaises(AttributeError):
            daten.hinweis = "anders"                      # type: ignore[misc]

    def test_note_eintragen_speichert_mit_stichtag(self):
        c, repository = controller()
        c.note_eintragen("MATHE", Decimal("1.3"))
        pl = repository.lade().modul("MATHE").pruefungsleistung
        self.assertEqual((pl.note, pl.bewertet_am), (Decimal("1.3"), STICHTAG_SKIZZE))
        self.assertEqual(repository.anzahl_speichervorgaenge, 1)

    def test_abgelehnte_eingabe_wird_nicht_gespeichert(self):
        c, repository = controller()
        with self.assertRaises(ValueError):
            c.note_eintragen("MATHE", Decimal("2.2"))
        with self.assertRaises(ValueError):
            c.phase_abgeben("MATHE")                      # keine Portfolio-Prüfung
        with self.assertRaises(ValueError):
            c.status_setzen("PY", Pruefungsstatus.ANGEMELDET)   # schon bestanden
        with self.assertRaises(ValueError):
            c.modul_zuordnen("GIBTSNICHT", 1)
        self.assertEqual(repository.anzahl_speichervorgaenge, 0)

    def test_erfassbare_module_auch_bewertete_zuerst_aus_semestern(self):
        c, _ = controller()
        kuerzel = [m.kuerzel for m in c.erfassbare_module()]
        self.assertEqual(kuerzel, ["BS", "MATHE", "OOP", "PY", "SEC", "WISS", "BA", "SIEM"])

    def test_note_mit_eigenem_datum_und_korrektur(self):
        c, repository = controller()
        c.note_eintragen("MATHE", Decimal("2.3"), date(2027, 1, 18))
        c.note_eintragen("MATHE", Decimal("1.3"), date(2027, 1, 19))  # Korrektur
        pl = repository.lade().modul("MATHE").pruefungsleistung
        self.assertEqual((pl.note, pl.bewertet_am), (Decimal("1.3"), date(2027, 1, 18)))

    def test_unplausible_gesamtzustaende_werden_abgelehnt(self):
        c, repository = controller()
        faelle = [
            ("Note in der Zukunft", lambda: c.note_eintragen("MATHE", Decimal("1.0"),
                                                             date(2027, 1, 21))),
            ("Note vor Studienbeginn", lambda: c.note_eintragen("MATHE", Decimal("1.0"),
                                                                date(2026, 8, 9))),
            ("Note ohne Semester", lambda: c.note_eintragen("BA", Decimal("1.0"))),
            ("Termin vor Studienbeginn", lambda: c.termin_setzen("MATHE", date(2026, 1, 1))),
            ("benotetes Modul aus dem Semester", lambda: c.modul_zuordnen("PY", 0)),
        ]
        for name, aktion in faelle:
            with self.subTest(name), self.assertRaises(ValueError):
                aktion()
        self.assertEqual(repository.anzahl_speichervorgaenge, 0)
        c.modul_zuordnen("PY", 2)                     # verschieben bleibt erlaubt

    def test_versuch_steht_im_dto(self):
        c, _ = controller()
        c.note_eintragen("MATHE", Decimal("5.0"))
        c.status_setzen("MATHE", Pruefungsstatus.ANGEMELDET)
        mathe = next(m for m in c.erfassbare_module() if m.kuerzel == "MATHE")
        self.assertEqual((mathe.versuch, mathe.max_versuche), (2, 3))

    def test_note_entfernen_ueber_den_controller(self):
        c, repository = controller()
        c.note_entfernen("PY")
        daten = c.dashboard_daten()
        self.assertEqual((daten.ects_bestanden, daten.ects_laufend), (20, 10))
        self.assertIn("«Einführung in die Programmierung mit Python»", daten.zusatz)
        with self.assertRaises(ValueError):
            c.note_entfernen("MATHE")                          # hat keine Note
        self.assertEqual(repository.anzahl_speichervorgaenge, 1)

    def test_termin_setzen_ueber_den_controller(self):
        c, repository = controller()
        c.termin_setzen("MATHE", date(2027, 2, 3))
        daten = c.dashboard_daten()
        self.assertIn("Klausur schreiben bis 03.02.2027 (noch 14 Tage)", daten.hinweis)
        self.assertEqual(repository.anzahl_speichervorgaenge, 1)

    def test_gescheitertes_speichern_laedt_den_gespeicherten_stand(self):
        sg = skizze()

        class KaputtesRepository(InMemoryStudiengangRepository):
            def speichere(self, _sg):
                raise OSError("Datei gesperrt")

            def lade(self):
                return skizze()

        c = DashboardController(KaputtesRepository(sg), KennzahlenService(),
                                ErfassungsService(), STICHTAG_SKIZZE)
        with self.assertRaises(OSError):
            c.note_eintragen("MATHE", Decimal("1.0"))
        self.assertEqual(c.dashboard_daten().ects_bestanden, 25)   # Änderung verworfen

    def test_weitere_pruefungsform_braucht_keine_aenderung_im_controller(self):
        c, repository = controller()
        sg = repository.lade()
        sg.semester(1).modul_zuordnen(sg.modul("BA"))
        daten = c.dashboard_daten()
        self.assertIn("Schriftliche Arbeit", [m.pruefungsform for m in daten.module])
        self.assertIsInstance(sg.modul("PY").pruefungsleistung, Klausur)


if __name__ == "__main__":
    unittest.main()
