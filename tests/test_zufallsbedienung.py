"""Zustandsbasierte Tests: Bedienfolgen durchspielen und nach jedem Schritt Regeln prüfen.

Der Test „drückt“ die Knöpfe des Erfassungsdialogs über genau die
Controller-Methoden, die auch die Knöpfe aufrufen, nur ohne Fenster:

1. Zufällige Bedienfolgen: Tausende Schritte mit zufälligem Modul, zufälliger
   Aktion und zufälliger Eingabe. Der Startwert ist fest, damit sich jeder
   gefundene Fehler genau nachspielen lässt.
2. Vollständige kurze Folgen: für jede Prüfungsform alle Folgen aus drei
   Aktionen.
3. Einmal je Knopf über die echte Oberfläche (übersprungen ohne Bildschirm).

Nach jedem Schritt prüft invarianten_pruefen() die Regeln, die immer gelten
müssen. Eine abgelehnte Eingabe (ValueError) ist erlaubt, darf den Zustand
aber nicht verändern. Jeder andere Fehler lässt den Test scheitern.

Protokoll: Mit der Umgebungsvariablen DASHBOARD_PROTOKOLL=pfad.csv schreibt
der Zufallstest jeden Schritt (Aktion, Eingabe, Ergebnis) in eine CSV-Datei.
"""

from __future__ import annotations

import copy
import csv
import itertools
import os
import random
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from controller import DashboardController
from domain import (MAX_VERSUCHE, ZULAESSIGE_NOTEN, Portfolio, Pruefungsstatus,
                    Studiengang)
from repository import InMemoryStudiengangRepository, SqliteStudiengangRepository
from service import ErfassungsService, KennzahlenService
from tests.test_repository import abbild
from werkzeuge.beispieldatenbank_erzeugen import DATEN, erzeuge_studiengang

STARTWERT = 20261010
SCHRITTE = 2000
RUNDREISE_ALLE = 250          # so oft wird zusätzlich über SQLite gespeichert und geladen
STICHTAG = date(2026, 10, 10)
NOTEN = sorted(ZULAESSIGE_NOTEN)
STATUS = (Pruefungsstatus.GEPLANT, Pruefungsstatus.ANGEMELDET, Pruefungsstatus.ABGEGEBEN)


_VORLAGE = erzeuge_studiengang(DATEN / "module.csv", DATEN / "stand.csv")


def _auszug(kuerzel: str) -> Studiengang:
    """Studiengang mit nur einem Modul der Vorlage; hält die vollständigen Folgen schnell."""
    vorlage = _VORLAGE.modul(kuerzel)
    sg = Studiengang(_VORLAGE.bezeichnung, _VORLAGE.abschluss, _VORLAGE.startdatum,
                     _VORLAGE.gesamt_ects)
    for semester in _VORLAGE.semester_liste:
        sg.neues_semester(semester.beginn, semester.ende)
    for ziel in _VORLAGE.ziele:
        sg.neues_ziel(copy.deepcopy(ziel))
    modul = sg.neues_modul(kuerzel, vorlage.bezeichnung, vorlage.ects,
                           copy.deepcopy(vorlage.pruefungsleistung))
    alt = _VORLAGE.semester_von(vorlage)
    if alt is not None:
        sg.semester(alt.nummer).modul_zuordnen(modul)
    return sg


def neuer_controller(kuerzel: str | None = None
                     ) -> tuple[DashboardController, InMemoryStudiengangRepository]:
    """Controller auf einer frischen Kopie der Beispieldaten (ganz oder ein Modul)."""
    sg = _auszug(kuerzel) if kuerzel else copy.deepcopy(_VORLAGE)
    repository = InMemoryStudiengangRepository(sg)
    controller = DashboardController(repository, KennzahlenService(), ErfassungsService(),
                                     STICHTAG)
    return controller, repository


def invarianten_pruefen(sg: Studiengang, controller: DashboardController) -> None:
    """Regeln, die nach jedem Schritt gelten müssen; wirft AssertionError."""
    zugeordnet: dict[int, int] = {}
    for semester in sg.semester_liste:
        for modul in semester.module:
            assert any(m is modul for m in sg.module), "Semester enthält fremdes Modul"
            assert id(modul) not in zugeordnet, f"{modul.kuerzel} in zwei Semestern"
            zugeordnet[id(modul)] = semester.nummer

    for modul in sg.module:
        pl = modul.pruefungsleistung
        assert 1 <= pl.versuchsnummer <= MAX_VERSUCHE, f"{modul.kuerzel}: Versuch"
        assert (pl.note is None) == (pl.bewertet_am is None), f"{modul.kuerzel}: Datum"
        if pl.note is None:
            assert pl.status not in (Pruefungsstatus.BESTANDEN,
                                     Pruefungsstatus.NICHT_BESTANDEN), modul.kuerzel
        else:
            assert pl.note in ZULAESSIGE_NOTEN, f"{modul.kuerzel}: Note {pl.note}"
            erwartet = (Pruefungsstatus.BESTANDEN if pl.note <= Decimal("4.0")
                        else Pruefungsstatus.NICHT_BESTANDEN)
            assert pl.status is erwartet, f"{modul.kuerzel}: {pl.status} zu Note {pl.note}"
        if not pl.ist_offen():
            assert pl.naechster_termin() is None, f"{modul.kuerzel}: Termin trotz Abschluss"
        if isinstance(pl, Portfolio):
            assert list(pl.phasenfristen) == sorted(pl.phasenfristen), modul.kuerzel
            if pl.phasenfristen:
                assert pl.abgegebene_phasen <= len(pl.phasenfristen), modul.kuerzel

    # Plausibilitätsregeln aus Phase 3 (Gesamtzustand über mehrere Eingaben)
    for modul in sg.module:
        pl = modul.pruefungsleistung
        if pl.bewertet_am is not None:
            assert sg.startdatum <= pl.bewertet_am <= STICHTAG, f"{modul.kuerzel}: Datum"
            assert sg.semester_von(modul) is not None, f"{modul.kuerzel}: Note ohne Semester"
        for termin in (getattr(pl, "pruefungstermin", None), getattr(pl, "abgabefrist", None),
                       *getattr(pl, "phasenfristen", ())):
            assert termin is None or termin >= sg.startdatum, f"{modul.kuerzel}: Termin"
        if isinstance(pl, Portfolio) and pl.note is not None and pl.phasenfristen:
            assert pl.abgegebene_phasen == len(pl.phasenfristen), f"{modul.kuerzel}: Phasen"

    bestanden = sum(m.ects for m in sg.module if m.ist_bestanden())
    assert sg.bestandene_ects() == bestanden

    # Die Anzeige muss sich in jedem Zustand aufbauen lassen.
    daten = controller.dashboard_daten()
    assert daten.ects_bestanden == bestanden
    assert daten.ects_bestanden + daten.ects_laufend <= sum(m.ects for m in sg.module)
    assert len(daten.notenverlauf) == sum(1 for m in sg.module if m.ist_bestanden())
    for b, l, g in daten.ects_je_semester:
        assert min(b, l, g) >= 0, "negative ECTS je Semester"
    assert len(controller.erfassbare_module()) == len(sg.module)


class ZufallsbedienungTest(unittest.TestCase):
    def test_zufaellige_bedienfolgen(self):
        zufall = random.Random(STARTWERT)
        controller, repository = neuer_controller()
        kuerzel = [m.kuerzel for m in repository.lade().module]
        protokoll = []
        zaehler = {"ok": 0, "abgelehnt": 0}

        def zufallsdatum() -> date:
            return STICHTAG + timedelta(days=zufall.randint(-120, 400))

        aktionen = {
            "note_eintragen": lambda k: (controller.note_eintragen,
                                         (k, zufall.choice(NOTEN), zufallsdatum())),
            "note_entfernen": lambda k: (controller.note_entfernen, (k,)),
            "status_setzen": lambda k: (controller.status_setzen, (k, zufall.choice(STATUS))),
            "phase_abgeben": lambda k: (controller.phase_abgeben, (k,)),
            "termin_setzen": lambda k: (controller.termin_setzen, (k, zufallsdatum())),
            "modul_zuordnen": lambda k: (controller.modul_zuordnen, (k, zufall.randint(0, 7))),
        }

        with tempfile.TemporaryDirectory() as ordner:
            sqlite = SqliteStudiengangRepository(Path(ordner) / "zufall.db")
            for schritt in range(1, SCHRITTE + 1):
                # Wenige Module häufiger wählen, damit lange Folgen am selben Modul entstehen.
                k = zufall.choice(kuerzel[:8]) if zufall.random() < 0.7 else zufall.choice(kuerzel)
                name = zufall.choice(sorted(aktionen))
                methode, argumente = aktionen[name](k)
                vorher = abbild(repository.lade())
                try:
                    methode(*argumente)
                    ergebnis = "ok"
                except ValueError as fehler:
                    ergebnis = f"abgelehnt: {fehler}"
                    self.assertEqual(abbild(repository.lade()), vorher,
                                     f"Schritt {schritt}: Ablehnung hat den Zustand geändert")
                except Exception as fehler:                 # pragma: no cover
                    self.fail(f"Schritt {schritt} ({name}{argumente}): unerwartet {fehler!r}")
                zaehler["ok" if ergebnis == "ok" else "abgelehnt"] += 1
                protokoll.append((schritt, name, *map(str, argumente), ergebnis))
                with self.subTest(schritt=schritt, aktion=name):
                    invarianten_pruefen(repository.lade(), controller)
                if schritt % RUNDREISE_ALLE == 0:
                    sqlite.speichere(repository.lade())
                    self.assertEqual(abbild(sqlite.lade()), abbild(repository.lade()),
                                     f"Schritt {schritt}: Rundreise über SQLite weicht ab")

        # Der Zufall muss beide Seiten treffen, sonst prüft der Test zu wenig.
        self.assertGreater(zaehler["ok"], SCHRITTE // 10)
        self.assertGreater(zaehler["abgelehnt"], SCHRITTE // 10)
        pfad = os.environ.get("DASHBOARD_PROTOKOLL")
        if pfad:
            with open(pfad, "w", newline="", encoding="utf-8") as datei:
                csv.writer(datei, delimiter=";").writerows(protokoll)

    def test_alle_folgen_aus_drei_aktionen_je_pruefungsform(self):
        """Je Prüfungsform ein Modul, alle 8^3 Folgen aus festen Aktionen."""
        aktionen = [
            ("Note 1,0", lambda c, k: c.note_eintragen(k, Decimal("1.0"))),
            ("Note 5,0", lambda c, k: c.note_eintragen(k, Decimal("5.0"))),
            ("Note entfernen", lambda c, k: c.note_entfernen(k)),
            ("geplant", lambda c, k: c.status_setzen(k, Pruefungsstatus.GEPLANT)),
            ("angemeldet", lambda c, k: c.status_setzen(k, Pruefungsstatus.ANGEMELDET)),
            ("abgegeben", lambda c, k: c.status_setzen(k, Pruefungsstatus.ABGEGEBEN)),
            ("Phase abgeben", lambda c, k: c.phase_abgeben(k)),
            ("Termin", lambda c, k: c.termin_setzen(k, STICHTAG + timedelta(days=14))),
        ]
        # Klausur, Advanced Workbook, Portfolio (mit Fristen), Portfolio (ohne Fristen),
        # schriftliche Arbeit
        module = ["P1-01", "P1-04", "P1-05", "P2-04", "P4-04"]
        laeufe = 0
        for kuerzel in module:
            for folge in itertools.product(aktionen, repeat=3):
                controller, repository = neuer_controller(kuerzel)
                for name, aktion in folge:
                    vorher = abbild(repository.lade())
                    try:
                        aktion(controller, kuerzel)
                    except ValueError:
                        self.assertEqual(abbild(repository.lade()), vorher,
                                         f"{kuerzel} {[n for n, _ in folge]}: Ablehnung "
                                         "hat den Zustand geändert")
                invarianten_pruefen(repository.lade(), controller)
                laeufe += 1
        self.assertEqual(laeufe, len(module) * len(aktionen) ** 3)


class DialogknoepfeTest(unittest.TestCase):
    """Betätigt jeden Knopf des echten Dialogs einmal (nur mit Bildschirm)."""

    def test_jeder_knopf_einmal(self):
        try:
            import tkinter as tk
            fenster = tk.Tk()
        except Exception as grund:              # kein tkinter oder kein Bildschirm
            self.skipTest(f"Oberfläche nicht verfügbar: {grund}")
        fehler = []
        fenster.report_callback_exception = lambda *info: fehler.append(info[1])
        try:
            from ui.dashboard_view import DashboardView
            controller, _ = neuer_controller()
            view = DashboardView(fenster, controller)
            view._oeffne_erfassung()
            dialog = view._dialog
            fenster.update()
            for kuerzel in ("P1-04", "P1-05", "P2-05"):
                index = [m.kuerzel for m in dialog._module].index(kuerzel)
                dialog._auswahl.current(index)
                dialog._zeige_modul()
                dialog._note.current(3)
                dialog._status.current(1)
                dialog._semester.current(2)
                for knopf in (dialog._note_knopf, dialog._entfernen_knopf,
                              dialog._termin_knopf, dialog._status_knopf, dialog._phase,
                              dialog._zuordnen_knopf):
                    knopf.invoke()             # ausgegraute Knöpfe tun nichts
                    fenster.update()
                    self.assertTrue(dialog._meldung["text"] or "disabled" in knopf.state())
        finally:
            fenster.destroy()
        self.assertEqual(fehler, [], "Fehler in einem Knopf-Ereignis")


if __name__ == "__main__":
    unittest.main()
