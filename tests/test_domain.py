"""Regeln der Entity-Klassen (Paket domain)."""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from domain import (Abschlussgrad, Abschlussziel, AdvancedWorkbook, Ampel, Klausur, Portfolio,
                    Pruefungsleistung, Pruefungsstatus, SchriftlicheArbeit, Studiengang)
from tests.beispiel import STICHTAG_SKIZZE, skizze


class PruefungsleistungTest(unittest.TestCase):
    def test_abstrakte_oberklasse_ist_nicht_instanziierbar(self):
        with self.assertRaises(TypeError):
            Pruefungsleistung()                          # type: ignore[abstract]

    def test_jede_unterklasse_liefert_ihren_termin(self):
        tag = date(2026, 11, 1)
        angemeldet = dict(status=Pruefungsstatus.ANGEMELDET)
        self.assertEqual(Klausur(tag, **angemeldet).naechster_termin(), tag)
        self.assertEqual(AdvancedWorkbook(tag, **angemeldet).naechster_termin(), tag)
        self.assertEqual(SchriftlicheArbeit(tag, **angemeldet).naechster_termin(), tag)
        portfolio = Portfolio([date(2026, 10, 1), tag], 1, **angemeldet)
        self.assertEqual(portfolio.naechster_termin(), tag)

    def test_zieltermin_gilt_nur_ohne_gebuchten_termin(self):
        geplant = date(2027, 2, 5)
        self.assertEqual(Klausur(None, zieltermin=geplant).naechster_termin(), geplant)
        self.assertEqual(Klausur(date(2027, 1, 30), zieltermin=geplant).naechster_termin(),
                         date(2027, 1, 30))

    def test_abgegebene_leistung_hat_keinen_naechsten_termin(self):
        workbook = AdvancedWorkbook(date(2026, 8, 30), status=Pruefungsstatus.ABGEGEBEN)
        self.assertIsNone(workbook.naechster_termin())

    def test_unzulaessige_notenstufe_wird_abgelehnt_und_nichts_geaendert(self):
        klausur = Klausur(date(2026, 9, 9), status=Pruefungsstatus.ANGEMELDET)
        for note in ("0.7", "2.2", "4.3"):
            with self.assertRaises(ValueError):
                klausur.note_eintragen(Decimal(note), date(2026, 9, 15))
        self.assertIsNone(klausur.note)
        self.assertIs(klausur.status, Pruefungsstatus.ANGEMELDET)

    def test_note_setzt_status_und_bewertungsdatum(self):
        klausur = Klausur(status=Pruefungsstatus.ANGEMELDET)
        klausur.note_eintragen(Decimal("4.0"), date(2026, 9, 15))
        self.assertIs(klausur.status, Pruefungsstatus.BESTANDEN)
        self.assertEqual(klausur.bewertet_am, date(2026, 9, 15))
        andere = Klausur(status=Pruefungsstatus.ANGEMELDET)
        andere.note_eintragen(Decimal("5.0"), date(2026, 9, 15))
        self.assertIs(andere.status, Pruefungsstatus.NICHT_BESTANDEN)

    def test_note_geht_aus_jedem_status(self):
        klausur = Klausur()                                   # geplant
        klausur.note_eintragen(Decimal("1.0"), date(2026, 9, 15))
        self.assertIs(klausur.status, Pruefungsstatus.BESTANDEN)

    def test_korrektur_ersetzt_note_und_behaelt_das_datum(self):
        klausur = Klausur(status=Pruefungsstatus.ANGEMELDET)
        klausur.note_eintragen(Decimal("5.0"), date(2026, 9, 15))
        klausur.note_eintragen(Decimal("4.0"), date(2026, 10, 1))   # Tippfehler berichtigt
        self.assertEqual((klausur.note, klausur.bewertet_am),
                         (Decimal("4.0"), date(2026, 9, 15)))
        self.assertIs(klausur.status, Pruefungsstatus.BESTANDEN)

    def test_note_entfernen_setzt_status_abgegeben(self):
        klausur = Klausur(status=Pruefungsstatus.ANGEMELDET, versuchsnummer=2)
        klausur.note_eintragen(Decimal("2.0"), date(2026, 9, 15))
        klausur.note_entfernen()
        self.assertEqual((klausur.note, klausur.bewertet_am), (None, None))
        self.assertIs(klausur.status, Pruefungsstatus.ABGEGEBEN)
        self.assertEqual(klausur.versuchsnummer, 2)
        with self.assertRaises(ValueError):
            klausur.note_entfernen()                          # keine Note mehr da

    def test_termin_setzen_je_pruefungsform(self):
        tag = date(2027, 2, 5)
        for pl, art in ((Klausur(), "Prüfungstermin"), (AdvancedWorkbook(), "Abgabefrist"),
                        (SchriftlicheArbeit(), "Abgabefrist"), (Portfolio(), "Frist Phase 1")):
            self.assertEqual(pl.terminart(), art)
            pl.termin_setzen(tag)
            self.assertEqual(pl.naechster_termin(), tag)

    def test_portfoliofristen_bleiben_aufsteigend(self):
        portfolio = Portfolio([date(2026, 9, 15), date(2026, 9, 30)], 1,
                              status=Pruefungsstatus.ANGEMELDET)
        portfolio.termin_setzen(date(2026, 10, 5))           # verschiebt Phase 2
        self.assertEqual(portfolio.phasenfristen, (date(2026, 9, 15), date(2026, 10, 5)))
        with self.assertRaises(ValueError):
            portfolio.termin_setzen(date(2026, 9, 1))         # vor Phase 1
        self.assertEqual(portfolio.naechster_termin(), date(2026, 10, 5))

    def test_termin_nur_fuer_offene_pruefungen(self):
        workbook = AdvancedWorkbook(date(2026, 8, 30), status=Pruefungsstatus.ABGEGEBEN)
        with self.assertRaises(ValueError):
            workbook.termin_setzen(date(2026, 9, 30))
        self.assertEqual(workbook.abgabefrist, date(2026, 8, 30))

    def test_bestanden_laesst_sich_nicht_von_hand_setzen(self):
        with self.assertRaises(ValueError):
            Klausur().status_setzen(Pruefungsstatus.BESTANDEN)

    def test_hoechstens_drei_versuche(self):
        klausur = Klausur(status=Pruefungsstatus.ANGEMELDET)
        for versuch in (1, 2, 3):
            self.assertEqual(klausur.versuchsnummer, versuch)
            klausur.note_eintragen(Decimal("5.0"), date(2026, 9, versuch))
            if versuch < 3:
                klausur.status_setzen(Pruefungsstatus.ANGEMELDET)
                self.assertIsNone(klausur.note)
        with self.assertRaises(ValueError):
            klausur.status_setzen(Pruefungsstatus.ANGEMELDET)
        self.assertEqual(klausur.versuchsnummer, 3)

    def test_gespeicherter_zustand_wird_im_konstruktor_geprueft(self):
        with self.assertRaises(ValueError):
            Klausur(status=Pruefungsstatus.BESTANDEN, note=Decimal("2.2"),
                    bewertet_am=date(2026, 9, 15))
        with self.assertRaises(ValueError):
            Klausur(status=Pruefungsstatus.BESTANDEN)          # bestanden ohne Note
        with self.assertRaises(ValueError):
            Klausur(versuchsnummer=4)

    def test_portfolio_phasen_bis_zur_abgabe(self):
        fristen = [date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 30)]
        portfolio = Portfolio(fristen, 2, status=Pruefungsstatus.ANGEMELDET)
        self.assertEqual(portfolio.naechste_aufgabe(), "Phase 3 abgeben")
        portfolio.phase_abgeben()
        self.assertIs(portfolio.status, Pruefungsstatus.ABGEGEBEN)
        self.assertIsNone(portfolio.naechster_termin())
        with self.assertRaises(ValueError):
            portfolio.phase_abgeben()

    def test_portfolio_ohne_fristen_ist_erlaubt(self):
        portfolio = Portfolio()                              # Multiplizität [0..*]
        self.assertEqual(portfolio.phasenfristen, ())
        self.assertIsNone(portfolio.naechster_termin())


class StudiengangTest(unittest.TestCase):
    def setUp(self):
        self.sg = skizze()

    def test_semester_folgen_im_halbjahrestakt(self):
        s1, s2 = self.sg.semester(1), self.sg.semester(2)
        self.assertEqual((s1.beginn, s1.ende), (date(2026, 8, 10), date(2027, 2, 9)))
        self.assertEqual(s2.beginn, date(2027, 2, 10))
        self.assertEqual(self.sg.aktuelles_semester(STICHTAG_SKIZZE), s1)

    def test_sollwert_ist_tagesgenau(self):
        self.assertEqual(self.sg.soll_ects(date(2026, 8, 10)), 0)
        self.assertEqual(self.sg.soll_ects(date(2027, 2, 10)), 30)
        # 163 von 184 Tagen des 1. Semesters
        self.assertAlmostEqual(float(self.sg.soll_ects(STICHTAG_SKIZZE)), 26.58, places=2)
        self.assertEqual(self.sg.soll_ects(date(2035, 1, 1)), 180)    # gedeckelt

    def test_durchschnitt_der_bestandenen_module(self):
        self.assertEqual(self.sg.bestandene_ects(), 25)
        self.assertEqual(self.sg.notendurchschnitt(), Decimal("2.00"))

    def test_modul_ist_im_katalog_und_im_semester_dasselbe_objekt(self):
        mathe = self.sg.modul("MATHE")
        self.assertIs(self.sg.semester_von(mathe), self.sg.semester(1))
        self.assertIsNone(self.sg.semester_von(self.sg.modul("BA")))

    def test_kuerzel_ist_eindeutig(self):
        with self.assertRaises(ValueError):
            self.sg.neues_modul("PY", "Doppelt", 5, Klausur())


class StudienzielTest(unittest.TestCase):
    def setUp(self):
        self.sg = skizze()
        self.abschluss, self.note = self.sg.ziele

    def test_ampel_rechnet_in_ganzen_modulen(self):
        # Soll 26,6 ECTS wird auf 25 abgerundet; 25 bestanden heißt auf Kurs.
        self.assertEqual(Abschlussziel.soll_in_modulstufen(Decimal("26.58")), 25)
        self.assertEqual(self.abschluss.abweichung(self.sg, STICHTAG_SKIZZE), 0)
        self.assertIs(self.abschluss.ampelstatus(self.sg, STICHTAG_SKIZZE), Ampel.GRUEN)

    def test_ampel_gelb_und_rot_beim_rueckstand(self):
        self.assertIs(self.abschluss.ampelstatus(self.sg, date(2027, 2, 10)), Ampel.GELB)
        self.assertIs(self.abschluss.ampelstatus(self.sg, date(2027, 4, 1)), Ampel.ROT)

    def test_notenziel_auf_der_toleranzgrenze_ist_gelb(self):
        self.assertEqual(self.note.abweichung(self.sg, STICHTAG_SKIZZE), Decimal("0.10"))
        self.assertIs(self.note.ampelstatus(self.sg, STICHTAG_SKIZZE), Ampel.GELB)
        self.assertEqual(self.note.restdurchschnitt(self.sg), Decimal("1.88"))

    def test_notenziel_ohne_note_ist_gruen(self):
        neu = Studiengang("Leer", Abschlussgrad.BACHELOR_OF_SCIENCE, date(2026, 8, 10))
        neu.neues_semester()
        self.assertIsNone(self.note.abweichung(neu, STICHTAG_SKIZZE))
        self.assertIs(self.note.ampelstatus(neu, STICHTAG_SKIZZE), Ampel.GRUEN)

    def test_prognose_beim_bisherigen_tempo(self):
        self.assertEqual(self.abschluss.prognose_semester(self.sg, date(2027, 2, 10)),
                         Decimal("7.2"))


if __name__ == "__main__":
    unittest.main()
