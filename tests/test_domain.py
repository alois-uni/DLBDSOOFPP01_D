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

    def test_selbst_geplant_nur_ohne_gebuchten_termin(self):
        geplant = date(2027, 2, 5)
        self.assertTrue(Klausur(None, zieltermin=geplant).ist_selbst_geplant())
        # gebuchter Termin am selben Tag wie der Zieltermin
        self.assertFalse(Klausur(geplant, zieltermin=geplant).ist_selbst_geplant())
        self.assertFalse(Klausur(None).ist_selbst_geplant())
        portfolio = Portfolio([geplant], 0, zieltermin=geplant,
                              status=Pruefungsstatus.ANGEMELDET)
        self.assertFalse(portfolio.ist_selbst_geplant())
        abgegeben = AdvancedWorkbook(None, zieltermin=geplant,
                                     status=Pruefungsstatus.ABGEGEBEN)
        self.assertFalse(abgegeben.ist_selbst_geplant())

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
        portfolio = Portfolio([date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 30)], 1,
                              status=Pruefungsstatus.ANGEMELDET)
        portfolio.termin_setzen(date(2026, 10, 5))           # verschiebt Phase 2
        self.assertEqual(portfolio.phasenfristen,
                         (date(2026, 9, 15), date(2026, 10, 5), date(2026, 10, 30)))
        for falsch in (date(2026, 9, 1), date(2026, 11, 5)):  # vor Phase 1, nach Phase 3
            with self.assertRaises(ValueError):
                portfolio.termin_setzen(falsch)
        self.assertEqual(portfolio.naechster_termin(), date(2026, 10, 5))

    def test_portfoliofristen_nacheinander_eintragen(self):
        portfolio = Portfolio()
        fristen = [date(2026, 11, 15), date(2026, 12, 15), date(2027, 1, 15)]
        for nr, frist in enumerate(fristen, start=1):
            self.assertEqual(portfolio.terminart(), f"Frist Phase {nr}")
            portfolio.termin_setzen(frist)
        self.assertEqual(portfolio.phasenfristen, tuple(fristen))
        # Alle drei bekannt: Termin setzen korrigiert die nächste offene Phase,
        # eine vierte Phase entsteht nicht.
        self.assertEqual(portfolio.terminart(), "Frist Phase 1")
        portfolio.termin_setzen(date(2026, 11, 20))
        self.assertEqual(portfolio.phasenfristen,
                         (date(2026, 11, 20), date(2026, 12, 15), date(2027, 1, 15)))

    def test_status_abgegeben_gibt_letzte_phase_ab(self):
        fristen = [date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 30)]
        portfolio = Portfolio(fristen, 2, status=Pruefungsstatus.ANGEMELDET)
        portfolio.status_setzen(Pruefungsstatus.ABGEGEBEN)
        self.assertEqual(portfolio.abgegebene_phasen, 3)
        portfolio.note_eintragen(Decimal("1.3"), date(2026, 11, 20))
        self.assertIs(portfolio.status, Pruefungsstatus.BESTANDEN)
        frueh = Portfolio(fristen, 1, status=Pruefungsstatus.ANGEMELDET)
        with self.assertRaises(ValueError):
            frueh.status_setzen(Pruefungsstatus.ABGEGEBEN)       # Phase 2 fehlt noch
        self.assertEqual((frueh.status, frueh.abgegebene_phasen),
                         (Pruefungsstatus.ANGEMELDET, 1))

    def test_zurueck_aus_abgegeben_oeffnet_phase_3(self):
        fristen = [date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 30)]
        portfolio = Portfolio(fristen, 3, status=Pruefungsstatus.ABGEGEBEN)
        portfolio.status_setzen(Pruefungsstatus.ANGEMELDET)
        self.assertEqual(portfolio.abgegebene_phasen, 2)
        self.assertEqual(portfolio.naechste_aufgabe(), "Phase 3 abgeben")   # keine Phase 4
        self.assertEqual(portfolio.terminart(), "Frist Phase 3")
        portfolio.termin_setzen(date(2026, 11, 6))
        self.assertEqual(portfolio.phasenfristen[-1], date(2026, 11, 6))
        self.assertEqual(len(portfolio.phasenfristen), 3)

    def test_portfolio_zustand_wird_im_konstruktor_geprueft(self):
        fristen = [date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 30)]
        with self.assertRaises(ValueError):
            Portfolio(fristen + [date(2026, 11, 30)])             # vier Phasen
        with self.assertRaises(ValueError):
            Portfolio(fristen, 2, status=Pruefungsstatus.ABGEGEBEN)
        with self.assertRaises(ValueError):
            Portfolio(fristen, 3, status=Pruefungsstatus.ANGEMELDET)

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

    def test_neuer_versuch_beginnt_ohne_alte_termine(self):
        # Sonst meldete Bereich G den Termin des alten Versuchs als überschritten.
        for pl in (Klausur(date(2026, 9, 9)), AdvancedWorkbook(date(2026, 9, 9)),
                   SchriftlicheArbeit(date(2026, 9, 9))):
            pl.status_setzen(Pruefungsstatus.ANGEMELDET)
            pl.note_eintragen(Decimal("5.0"), date(2026, 9, 20))
            pl.status_setzen(Pruefungsstatus.ANGEMELDET)
            self.assertEqual(pl.versuchsnummer, 2)
            self.assertIsNone(pl.naechster_termin(), pl.FORM)

    def test_neuer_versuch_beginnt_portfolio_mit_phase_1(self):
        fristen = [date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 1)]
        portfolio = Portfolio(fristen, 3, status=Pruefungsstatus.ABGEGEBEN,
                              zieltermin=date(2027, 3, 1))
        portfolio.note_eintragen(Decimal("5.0"), date(2026, 10, 9))
        portfolio.status_setzen(Pruefungsstatus.ANGEMELDET)
        self.assertEqual((portfolio.phasenfristen, portfolio.abgegebene_phasen), ((), 0))
        self.assertEqual(portfolio.terminart(), "Frist Phase 1")
        self.assertEqual(portfolio.zieltermin, date(2027, 3, 1))   # Zieltermin bleibt

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

    def test_terminart_nach_letzter_phase(self):
        fristen = [date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 30)]
        portfolio = Portfolio(fristen, 2, status=Pruefungsstatus.ANGEMELDET)
        self.assertEqual(portfolio.terminart(), "Frist Phase 3")
        portfolio.phase_abgeben()
        self.assertEqual(portfolio.terminart(), "Phasenfrist")   # nicht "Frist Phase 4"

    def test_portfolio_note_erst_nach_letzter_phase(self):
        portfolio = Portfolio([date(2026, 9, 15), date(2026, 9, 30), date(2026, 10, 1)], 2,
                              status=Pruefungsstatus.ANGEMELDET)
        with self.assertRaises(ValueError):
            portfolio.note_eintragen(Decimal("1.0"), date(2026, 10, 1))
        portfolio.phase_abgeben()
        portfolio.note_eintragen(Decimal("1.0"), date(2026, 10, 1))
        self.assertIs(portfolio.status, Pruefungsstatus.BESTANDEN)

    def test_portfolio_ohne_fristen_ist_erlaubt(self):
        portfolio = Portfolio()                              # Multiplizität [0..3]
        self.assertEqual(portfolio.phasenfristen, ())
        self.assertIsNone(portfolio.naechster_termin())

    def test_phase_abgeben_braucht_bekannte_frist(self):
        portfolio = Portfolio(status=Pruefungsstatus.ANGEMELDET)
        with self.assertRaises(ValueError):
            portfolio.phase_abgeben()                    # Frist von Phase 1 fehlt
        self.assertEqual(portfolio.abgegebene_phasen, 0)
        portfolio.termin_setzen(date(2026, 11, 1))       # Frist Phase 1
        portfolio.phase_abgeben()
        self.assertIs(portfolio.status, Pruefungsstatus.ANGEMELDET)   # 2 Phasen fehlen
        self.assertEqual(portfolio.terminart(), "Frist Phase 2")
        with self.assertRaises(ValueError):
            portfolio.phase_abgeben()                    # Frist von Phase 2 fehlt
        self.assertEqual(portfolio.abgegebene_phasen, 1)
        with self.assertRaises(ValueError):
            Portfolio([], 2)                             # gespeicherter Widerspruch

    def test_portfolio_ohne_fristen_bekommt_keine_note(self):
        portfolio = Portfolio()
        with self.assertRaises(ValueError):
            portfolio.note_eintragen(Decimal("1.0"), date(2026, 10, 1))
        self.assertIs(portfolio.status, Pruefungsstatus.GEPLANT)
        self.assertIsNone(portfolio.note)


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
