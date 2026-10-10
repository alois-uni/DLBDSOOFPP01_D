"""
Machbarkeitstest 3 - Rechenlogik der beiden Studienziele
========================================================
Leitfrage: Lassen sich die unter Punkt 1 definierten Ziele ueberhaupt
in ueberpruefbare Kennzahlen uebersetzen?

Geprueft werden die drei nicht-trivialen Rechenwege des Dashboards:

  Z1 Regelstudienzeit  -> ECTS-Soll/Ist-Vergleich und Abschlussprognose
  Z2 Notenziel         -> ECTS-gewichteter Durchschnitt
  Z2 Steuerungsgroesse -> notwendiger Durchschnitt der Restmodule

Die Pruefung erfolgt mit unittest aus der Standardbibliothek, also ohne
pytest oder eine andere Fremdbibliothek.
"""

from __future__ import annotations

import unittest
from decimal import Decimal, ROUND_HALF_UP

GESAMT_ECTS = 180
REGELSTUDIENZEIT_SEMESTER = 6
ECTS_PRO_SEMESTER = GESAMT_ECTS // REGELSTUDIENZEIT_SEMESTER  # 30


def gewichteter_durchschnitt(noten: list[tuple[Decimal, int]]) -> Decimal | None:
    """
    ECTS-gewichteter Notendurchschnitt.

    noten: Liste aus (Note, ECTS) je bewertetem Modul.
    Rueckgabe: None, solange noch kein Modul bewertet ist.

    Decimal statt float, weil Noten exakte Dezimalwerte sind und sich
    Rundungsfehler bei einem Zielwert von 1,9 unmittelbar auf die
    Ampelfarbe des Dashboards auswirken wuerden.
    """
    if not noten:
        return None
    summe = sum(note * ects for note, ects in noten)
    gewicht = sum(ects for _, ects in noten)
    return (summe / gewicht).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def benoetigter_restdurchschnitt(
    noten: list[tuple[Decimal, int]], zielnote: Decimal
) -> Decimal | None:
    """
    Welchen Durchschnitt muessen die noch offenen ECTS haben, damit das
    Notenziel am Ende des Studiums genau erreicht wird?

    Das ist die eigentliche Steuerungsgroesse des Dashboards: Sie sagt
    nicht nur, wo man steht, sondern was noch zu tun ist.

    Rueckgabe:
        Decimal  - der noetige Durchschnitt
        None     - wenn keine ECTS mehr offen sind
    Ein Wert < 1,0 bedeutet, dass das Ziel rechnerisch nicht mehr
    erreichbar ist; ein Wert > 4,0 bedeutet, dass es kaum noch
    verfehlt werden kann.
    """
    erreichte_ects = sum(ects for _, ects in noten)
    rest_ects = GESAMT_ECTS - erreichte_ects
    if rest_ects <= 0:
        return None
    summe_ist = sum(note * ects for note, ects in noten)
    summe_soll = zielnote * GESAMT_ECTS
    return ((summe_soll - summe_ist) / rest_ects).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def ects_soll(verstrichene_semester: int) -> int:
    """Soll-ECTS bei gleichmaessigem Studienfortschritt in Regelstudienzeit."""
    return min(verstrichene_semester * ECTS_PRO_SEMESTER, GESAMT_ECTS)


def prognose_semester(erreichte_ects: int, verstrichene_semester: int) -> Decimal | None:
    """
    Lineare Hochrechnung: Wie viele Semester dauert das Studium beim
    bisherigen Tempo insgesamt?

    Rueckgabe None, solange noch keine Datengrundlage existiert
    (kein abgeschlossenes Semester oder noch keine ECTS).
    """
    if verstrichene_semester <= 0 or erreichte_ects <= 0:
        return None
    tempo = Decimal(erreichte_ects) / Decimal(verstrichene_semester)
    return (Decimal(GESAMT_ECTS) / tempo).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


class TestZielkennzahlen(unittest.TestCase):
    """Nachweis, dass die Kennzahlen korrekt und randfallsicher rechnen."""

    def test_durchschnitt_gewichtet_nach_ects(self):
        # 1,0 auf 10 ECTS und 3,0 auf 5 ECTS -> (10+15)/15 = 1,67
        noten = [(Decimal("1.0"), 10), (Decimal("3.0"), 5)]
        self.assertEqual(gewichteter_durchschnitt(noten), Decimal("1.67"))

    def test_durchschnitt_ohne_noten_ist_none(self):
        self.assertIsNone(gewichteter_durchschnitt([]))

    def test_restdurchschnitt_bei_studienstart(self):
        # Noch nichts bewertet: der Restdurchschnitt entspricht dem Ziel.
        self.assertEqual(
            benoetigter_restdurchschnitt([], Decimal("1.9")), Decimal("1.90")
        )

    def test_restdurchschnitt_puffer_nach_guter_note(self):
        # Eine 1,0 auf 5 ECTS schafft Puffer: erlaubt ist nun mehr als 1,9.
        noten = [(Decimal("1.0"), 5)]
        self.assertGreater(
            benoetigter_restdurchschnitt(noten, Decimal("1.9")), Decimal("1.9")
        )

    def test_restdurchschnitt_warnung_nach_schlechter_note(self):
        # Eine 3,7 auf 5 ECTS kostet Puffer: erlaubt ist nun weniger als 1,9.
        noten = [(Decimal("3.7"), 5)]
        self.assertLess(
            benoetigter_restdurchschnitt(noten, Decimal("1.9")), Decimal("1.9")
        )

    def test_restdurchschnitt_am_studienende_ist_none(self):
        noten = [(Decimal("2.0"), GESAMT_ECTS)]
        self.assertIsNone(benoetigter_restdurchschnitt(noten, Decimal("1.9")))

    def test_ects_soll_waechst_linear_und_deckelt_bei_180(self):
        self.assertEqual(ects_soll(1), 30)
        self.assertEqual(ects_soll(6), 180)
        self.assertEqual(ects_soll(9), 180)

    def test_prognose_bei_planmaessigem_tempo(self):
        # 30 ECTS nach einem Semester -> Hochrechnung exakt 6 Semester.
        self.assertEqual(prognose_semester(30, 1), Decimal("6.0"))

    def test_prognose_bei_halbem_tempo(self):
        self.assertEqual(prognose_semester(15, 1), Decimal("12.0"))

    def test_prognose_ohne_datengrundlage_ist_none(self):
        self.assertIsNone(prognose_semester(0, 1))
        self.assertIsNone(prognose_semester(30, 0))


if __name__ == "__main__":
    print("Beispielrechnung fuer den aktuellen Studienstand")
    print("-------------------------------------------------")
    beispiel = [(Decimal("1.7"), 5)]
    print(f"  Notendurchschnitt          : {gewichteter_durchschnitt(beispiel)}")
    print(f"  Noetiger Restdurchschnitt  : "
          f"{benoetigter_restdurchschnitt(beispiel, Decimal('1.9'))} (Ziel 1,9)")
    print(f"  Soll-ECTS nach 1 Semester  : {ects_soll(1)}")
    print(f"  Prognose bei 5 ECTS/Sem.   : {prognose_semester(5, 1)} Semester")
    print()
    unittest.main(verbosity=2)
