"""Tiefentest: sucht Fehler über lange Eingabefolgen und viele Grenzfälle.

Ergänzt die unittest-Tests in tests/. Er läuft deutlich länger, deshalb
gehört er nicht zu "py -m unittest", sondern wird von Hand gestartet:

    py werkzeuge/tiefentest.py                  Standardumfang (einige Minuten)
    py werkzeuge/tiefentest.py --schnell        kleiner Umfang (unter einer Minute)
    py werkzeuge/tiefentest.py --gruendlich     großer Umfang (deutlich länger)
    py werkzeuge/tiefentest.py --nur zustaende,zufall --tiefe 10
    py werkzeuge/tiefentest.py --bericht bericht.txt
    py werkzeuge/tiefentest.py --ohne-fenster   ohne tkinter-Fenster

Während der Teile zustaende und oberflaeche gehen kurz Fenster auf und zu;
das ist gewollt. Mit --ohne-fenster bleibt der Bildschirm ruhig, dann
entfällt aber die Prüfung der Darstellung.

Unter macOS und Linux python3 statt py.

Teile (Auswahl mit --nur):

zustaende   Für je ein Modul jeder Prüfungsform und Ausgangslage werden alle
            Zustände gesucht, die sich mit den Knöpfen des Dialogs erreichen
            lassen (Breitensuche bis --tiefe Schritte). Zu jedem Fehler kommt
            so die kürzeste Eingabefolge heraus. Zusätzlich wird geprüft, ob
            ein Modul aus jedem Zustand noch bestanden werden kann (Sackgasse).
zufall      Lange zufällige Bedienfolgen am ganzen Studiengang, mehrere Module
            durcheinander. Eine gefundene Fehlerfolge wird so lange gekürzt,
            wie der Fehler bleibt.
stichtage   Die Anzeige für viele Stichtage, vom Tag vor Studienbeginn bis
            lange nach der Regelstudienzeit.
kalender    Semestergrenzen und Sollwert für viele Studienbeginne,
            darunter Monatsenden und der 29. Februar.
datenbank   Speichern und Laden über die Datei, ein Fehler mitten im
            Speichern, zwei gleichzeitig geöffnete Dashboards.
oberflaeche Echte Fenster: Dashboard in mehreren Größen, überlappende Texte,
            Zufallsfolgen über die Knöpfe und Eingabefelder des Dialogs.
            Läuft nur mit tkinter und Bildschirm.

Nach jedem gelungenen Schritt prüft der Test:
* die Regeln, die immer gelten (Status passt zur Note, höchstens drei
  Versuche, Fristen aufsteigend, nicht mehr abgegebene Phasen als Fristen,
  höchstens drei Phasen je Portfolio ...)
* die Wirkung des Schritts (die eingetragene Note steht danach am Modul, ein
  gesetzter Termin ist der nächste Termin ...)
* Speichern und Laden über SQLite ergibt denselben Zustand und dieselbe Anzeige
* die Anzeige lässt sich für mehrere Stichtage aufbauen, die Kennzahlen liegen
  in ihren Grenzen
Eine abgelehnte Eingabe (ValueError) ist erlaubt, darf aber nichts ändern.

Ergebnis: Liste der Befunde mit der kürzesten gefundenen Eingabefolge.
FEHLER sind Verstöße gegen Regeln, HINWEISE sind Auffälligkeiten, die
gewollt sein können. Rückgabewert 1, wenn es FEHLER gibt, sonst 0.
"""

from __future__ import annotations

import argparse
import copy
import random
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

PROGRAMMORDNER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROGRAMMORDNER))          # Pakete auch beim direkten Aufruf finden

from controller import DashboardController  # noqa: E402
from domain import (MAX_VERSUCHE, PHASEN_JE_PORTFOLIO, ZULAESSIGE_NOTEN,  # noqa: E402
                    Abschlussgrad, Notenziel, Portfolio, Pruefungsstatus, Studiengang)
from domain.studiengang import _plus_monate  # noqa: E402
from repository import (InMemoryStudiengangRepository,  # noqa: E402
                        SqliteStudiengangRepository)
from service import ErfassungsService, KennzahlenService  # noqa: E402

BEISPIEL_DB = PROGRAMMORDNER / "daten" / "beispiel.db"
# Stand der Beispieldaten: das letzte Bewertungsdatum, frühestens der 10.10.2026.
STICHTAG = max([date(2026, 10, 10)] + [
    m.pruefungsleistung.bewertet_am for m in SqliteStudiengangRepository(BEISPIEL_DB).lade().module
    if m.pruefungsleistung.bewertet_am is not None])
STATUS = (Pruefungsstatus.GEPLANT, Pruefungsstatus.ANGEMELDET, Pruefungsstatus.ABGEGEBEN)
NOTEN = sorted(ZULAESSIGE_NOTEN)
GRENZE = Decimal("4.0")

UMFANG = {           # tiefe, zufall_laeufe, zufall_laenge, dialog_schritte
    "schnell": (6, 150, 40, 150),
    "standard": (10, 600, 80, 600),
    "gruendlich": (12, 3000, 150, 2500),
}


# ====================================================================== Befunde
@dataclass
class Befund:
    """Ein gefundener Fehler mit der kürzesten Eingabefolge, die ihn auslöst."""
    schwere: str                 # "FEHLER" oder "HINWEIS"
    teil: str
    art: str
    text: str
    folge: tuple[str, ...]
    ausgangslage: str = ""
    anzahl: int = 1


@dataclass
class Sammlung:
    """Sammelt Befunde; gleiche Befunde werden gezählt, die kürzeste Folge bleibt."""
    befunde: dict[tuple, Befund] = field(default_factory=dict)

    def melde(self, schwere: str, teil: str, art: str, text: str,
              folge: tuple[str, ...] = (), ausgangslage: str = "") -> None:
        if teil == "oberflaeche" and len(folge) > 25:      # Protokoll: nur das Ende zählt
            folge = ("…",) + tuple(folge[-25:])
        # Zahlen und Daten im Text gleichsetzen, damit derselbe Fehler mit
        # anderen Werten nicht als neuer Befund zählt.
        schluessel = (schwere, teil, art, re.sub(r"\d+", "#", text))
        alt = self.befunde.get(schluessel)
        if alt is None:
            self.befunde[schluessel] = Befund(schwere, teil, art, text, tuple(folge),
                                              ausgangslage)
            return
        alt.anzahl += 1
        if len(folge) < len(alt.folge):
            alt.text, alt.folge, alt.ausgangslage = text, tuple(folge), ausgangslage

    def anzahl(self, schwere: str) -> int:
        return sum(1 for b in self.befunde.values() if b.schwere == schwere)


# ====================================================================== Schritte
# Ein Schritt ist ein Tupel aus Daten, damit er sich nachspielen, kürzen und
# lesbar ausgeben lässt: ("note", Decimal, date), ("entfernen",),
# ("status", Pruefungsstatus), ("phase",), ("termin", date), ("semester", int).

def schritt_text(schritt: tuple) -> str:
    art, *werte = schritt
    if art == "note":
        return f"Note {str(werte[0]).replace('.', ',')} mit Datum {werte[1]:%d.%m.%Y}"
    if art == "entfernen":
        return "Note entfernen"
    if art == "status":
        return f"Status „{werte[0].anzeige}“"
    if art == "phase":
        return "Nächste Phase abgeben"
    if art == "termin":
        return f"Termin/Frist setzen auf {werte[0]:%d.%m.%Y}"
    if art == "semester":
        return "aus dem Semester nehmen" if werte[0] == 0 else f"dem {werte[0]}. Semester zuordnen"
    return repr(schritt)


def ausfuehren(controller: DashboardController, kuerzel: str, schritt: tuple) -> None:
    """Ruft dieselbe Controller-Methode auf wie der passende Dialogknopf."""
    art, *werte = schritt
    if art == "note":
        controller.note_eintragen(kuerzel, werte[0], werte[1])
    elif art == "entfernen":
        controller.note_entfernen(kuerzel)
    elif art == "status":
        controller.status_setzen(kuerzel, werte[0])
    elif art == "phase":
        controller.phase_abgeben(kuerzel)
    elif art == "termin":
        controller.termin_setzen(kuerzel, werte[0])
    elif art == "semester":
        controller.modul_zuordnen(kuerzel, werte[0])
    else:
        raise AssertionError(f"unbekannter Schritt {schritt}")


def schritte_fuer_suche(sg: Studiengang) -> list[tuple]:
    """Feste, kleine Auswahl an Eingaben, damit die Zahl der Zustände endlich bleibt.

    Die Daten liegen an den Grenzen der Regeln: vor und am Studienbeginn,
    am Stichtag, kurz und lange danach.
    """
    beginn = sg.startdatum
    tage = [beginn - timedelta(days=1), beginn, STICHTAG, STICHTAG + timedelta(days=20),
            STICHTAG + timedelta(days=200)]
    schritte: list[tuple] = []
    for note in (Decimal("1.0"), Decimal("4.0"), Decimal("5.0")):
        for tag in tage[:4]:
            schritte.append(("note", note, tag))
    schritte.append(("entfernen",))
    schritte += [("status", s) for s in STATUS]
    schritte.append(("phase",))
    schritte += [("termin", tag) for tag in tage]
    schritte += [("semester", nr) for nr in (0, 1, 2, sg.regelstudienzeit(),
                                             sg.regelstudienzeit() + 1)]
    return schritte


def zufallsschritt(zufall: random.Random, sg: Studiengang) -> tuple:
    """Beliebige Eingabe, auch Daten weit außerhalb und alle Notenstufen."""
    def tag() -> date:
        wahl = zufall.random()
        if wahl < 0.6:
            return STICHTAG + timedelta(days=zufall.randint(-90, 120))
        if wahl < 0.8:
            return sg.startdatum + timedelta(days=zufall.randint(-3, 3))
        return STICHTAG + timedelta(days=zufall.randint(-800, 2500))

    art = zufall.choice(("note", "note", "entfernen", "status", "status", "phase",
                         "phase", "termin", "termin", "semester"))
    if art == "note":
        return ("note", zufall.choice(NOTEN), tag())
    if art == "status":
        return ("status", zufall.choice(STATUS))
    if art == "termin":
        return ("termin", tag())
    if art == "semester":
        return ("semester", zufall.randint(0, sg.regelstudienzeit() + 1))
    return (art,)


# ====================================================================== Zustand
def pl_abbild(pl) -> tuple:
    return (type(pl).__name__, pl.bezeichnung, pl.status.value, pl.versuchsnummer, pl.note,
            pl.bewertet_am, pl.zieltermin, getattr(pl, "pruefungstermin", None),
            getattr(pl, "abgabefrist", None), tuple(getattr(pl, "phasenfristen", ())),
            getattr(pl, "abgegebene_phasen", None))


def abbild(sg: Studiengang) -> tuple:
    """Vollständiger, vergleichbarer Zustand des Studiengangs."""
    semester = tuple((s.nummer, s.beginn, s.ende, tuple(m.kuerzel for m in s.module))
                     for s in sg.semester_liste)
    module = tuple((m.kuerzel, m.bezeichnung, m.ects, pl_abbild(m.pruefungsleistung))
                   for m in sg.module)
    ziele = tuple((type(z).__name__, z.bezeichnung, z.toleranz, z.ist_aktiv)
                  for z in sg.ziele)
    return (sg.bezeichnung, sg.abschluss, sg.startdatum, sg.gesamt_ects, semester, module, ziele)


def modul_vorher(sg: Studiengang, kuerzel: str) -> dict:
    modul = sg.modul(kuerzel)
    pl = modul.pruefungsleistung
    semester = sg.semester_von(modul)
    return dict(status=pl.status, versuch=pl.versuchsnummer, note=pl.note,
                bewertet_am=pl.bewertet_am, terminart=pl.terminart(),
                fristen=tuple(getattr(pl, "phasenfristen", ())),
                phasen=getattr(pl, "abgegebene_phasen", None),
                semester=semester.nummer if semester else None)


def controller_fuer(sg: Studiengang, stichtag: date = STICHTAG) -> DashboardController:
    return DashboardController(InMemoryStudiengangRepository(sg), KennzahlenService(),
                               ErfassungsService(), stichtag)


def lade_beispiel() -> Studiengang:
    return SqliteStudiengangRepository(BEISPIEL_DB).lade()


def auszug(vorlage: Studiengang, kuerzel: str) -> Studiengang:
    """Studiengang mit nur einem Modul der Vorlage; hält die Zustandssuche klein."""
    alt = vorlage.modul(kuerzel)
    sg = Studiengang(vorlage.bezeichnung, vorlage.abschluss, vorlage.startdatum,
                     vorlage.gesamt_ects)
    for semester in vorlage.semester_liste:
        sg.neues_semester(semester.beginn, semester.ende)
    for ziel in vorlage.ziele:
        sg.neues_ziel(copy.deepcopy(ziel))
    modul = sg.neues_modul(alt.kuerzel, alt.bezeichnung, alt.ects,
                           copy.deepcopy(alt.pruefungsleistung))
    semester = vorlage.semester_von(alt)
    if semester is not None:
        sg.semester(semester.nummer).modul_zuordnen(modul)
    return sg


def beschreibe(sg: Studiengang, kuerzel: str) -> str:
    m = sg.modul(kuerzel)
    pl = m.pruefungsleistung
    teile = [f"{m.kuerzel} «{m.bezeichnung}»", pl.FORM, pl.status.anzeige]
    if pl.note is not None:
        teile.append(f"Note {pl.note}")
    if isinstance(pl, Portfolio):
        teile.append(pl.phasenstand() if pl.phasenfristen else "ohne Fristen")
    semester = sg.semester_von(m)
    teile.append(f"{semester.nummer}. Semester" if semester else "keinem Semester zugeordnet")
    return ", ".join(teile)


# ====================================================================== Prüfungen
def regeln_pruefen(sg: Studiengang, stichtag: date = STICHTAG) -> list[tuple[str, str]]:
    """Regeln, die in jedem Zustand gelten müssen. Liefert (Art, Text)."""
    fehler = []
    gesehen: dict[int, int] = {}
    for semester in sg.semester_liste:
        for modul in semester.module:
            if not any(m is modul for m in sg.module):
                fehler.append(("Struktur", f"{modul.kuerzel}: Semester hält fremdes Modulobjekt"))
            if id(modul) in gesehen:
                fehler.append(("Struktur", f"{modul.kuerzel} in zwei Semestern"))
            gesehen[id(modul)] = semester.nummer
    for modul in sg.module:
        pl, k = modul.pruefungsleistung, modul.kuerzel
        if not 1 <= pl.versuchsnummer <= MAX_VERSUCHE:
            fehler.append(("Versuche", f"{k}: Versuch {pl.versuchsnummer}"))
        if (pl.note is None) != (pl.bewertet_am is None):
            fehler.append(("Note/Datum", f"{k}: Note {pl.note} mit Datum {pl.bewertet_am}"))
        if pl.note is None and pl.status in (Pruefungsstatus.BESTANDEN,
                                             Pruefungsstatus.NICHT_BESTANDEN):
            fehler.append(("Status/Note", f"{k}: Status {pl.status.value} ohne Note"))
        if pl.note is not None:
            if pl.note not in ZULAESSIGE_NOTEN:
                fehler.append(("Note", f"{k}: unzulässige Note {pl.note}"))
            soll = (Pruefungsstatus.BESTANDEN if pl.note <= GRENZE
                    else Pruefungsstatus.NICHT_BESTANDEN)
            if pl.status is not soll:
                fehler.append(("Status/Note", f"{k}: Status {pl.status.value} bei Note {pl.note}"))
            if sg.semester_von(modul) is None:
                fehler.append(("Plausibilität", f"{k}: Note ohne Semester"))
            if not sg.startdatum <= pl.bewertet_am:
                fehler.append(("Plausibilität",
                               f"{k}: Bewertung {pl.bewertet_am} vor Studienbeginn"))
            if pl.bewertet_am > stichtag:
                fehler.append(("Plausibilität", f"{k}: Bewertung {pl.bewertet_am} nach dem "
                                                f"Stichtag {stichtag}"))
        if not pl.ist_offen() and pl.naechster_termin() is not None:
            fehler.append(("Termin", f"{k}: nächster Termin trotz Status {pl.status.value}"))
        for termin in (getattr(pl, "pruefungstermin", None), getattr(pl, "abgabefrist", None),
                       *getattr(pl, "phasenfristen", ())):
            if termin is not None and termin < sg.startdatum:
                fehler.append(("Plausibilität", f"{k}: Termin {termin} vor Studienbeginn"))
        if isinstance(pl, Portfolio):
            fristen = list(pl.phasenfristen)
            if fristen != sorted(fristen):
                fehler.append(("Portfolio", f"{k}: Fristen nicht aufsteigend {fristen}"))
            if not 0 <= pl.abgegebene_phasen <= len(fristen):
                fehler.append(("Portfolio", f"{k}: {pl.abgegebene_phasen} abgegebene Phasen "
                                            f"bei {len(fristen)} Fristen"))
            if len(fristen) > PHASEN_JE_PORTFOLIO:
                fehler.append(("Portfolio", f"{k}: {len(fristen)} Phasenfristen"))
            if pl.note is not None and pl.abgegebene_phasen != PHASEN_JE_PORTFOLIO:
                fehler.append(("Portfolio", f"{k}: Note bei {pl.phasenstand()}"))
            if pl.ist_offen() != (pl.abgegebene_phasen < PHASEN_JE_PORTFOLIO):
                fehler.append(("Portfolio", f"{k}: Status {pl.status.value} bei "
                                            f"{pl.phasenstand()}"))
    return fehler


def wirkung_pruefen(sg: Studiengang, kuerzel: str, schritt: tuple, vorher: dict) -> list[str]:
    """Hat ein gelungener Schritt genau das bewirkt, was der Knopf verspricht?"""
    modul = sg.modul(kuerzel)
    pl = modul.pruefungsleistung
    art, *werte = schritt
    fehler = []
    if art == "note":
        note, tag = werte
        if pl.note != note:
            fehler.append(f"Note ist {pl.note} statt {note}")
        erwartet = vorher["bewertet_am"] if vorher["note"] is not None else tag
        if pl.bewertet_am != erwartet:
            fehler.append(f"Bewertungsdatum {pl.bewertet_am} statt {erwartet}")
    elif art == "entfernen":
        if pl.note is not None or pl.status is not Pruefungsstatus.ABGEGEBEN:
            fehler.append(f"nach Note entfernen: Note {pl.note}, Status {pl.status.value}")
        if pl.versuchsnummer != vorher["versuch"]:
            fehler.append("Note entfernen hat den Versuch geändert")
    elif art == "status":
        if pl.status is not werte[0]:
            fehler.append(f"Status ist {pl.status.value} statt {werte[0].value}")
        neuer_versuch = vorher["status"] is Pruefungsstatus.NICHT_BESTANDEN
        if pl.versuchsnummer != vorher["versuch"] + (1 if neuer_versuch else 0):
            fehler.append(f"Versuch {vorher['versuch']} -> {pl.versuchsnummer}")
        if (isinstance(pl, Portfolio) and werte[0] is Pruefungsstatus.ABGEGEBEN
                and pl.abgegebene_phasen != PHASEN_JE_PORTFOLIO):
            fehler.append(f"Portfolio abgegeben bei {pl.phasenstand()}")
        if neuer_versuch:
            alt = [t for t in (getattr(pl, "pruefungstermin", None),
                               getattr(pl, "abgabefrist", None), *getattr(pl, "phasenfristen", ()))
                   if t is not None]
            if alt or getattr(pl, "abgegebene_phasen", 0):
                fehler.append(f"neuer Versuch übernimmt Termine/Phasen des alten: {alt}, "
                              f"{getattr(pl, 'abgegebene_phasen', 0)} Phasen")
    elif art == "phase":
        if pl.abgegebene_phasen != vorher["phasen"] + 1:
            fehler.append(f"abgegebene Phasen {vorher['phasen']} -> {pl.abgegebene_phasen}")
    elif art == "termin":
        tag = werte[0]
        treffer = re.match(r"Frist Phase (\d+)", vorher["terminart"])
        # Beim Portfolio lassen sich auch die Fristen späterer Phasen eintragen;
        # nächster Termin wird nur die Frist der nächsten offenen Phase.
        naechste_phase = treffer is None or int(treffer.group(1)) == vorher["phasen"] + 1
        if naechste_phase and pl.naechster_termin() != tag:
            fehler.append(f"nächster Termin ist {pl.naechster_termin()} statt {tag}")
        if treffer:
            nr = int(treffer.group(1))
            fristen = pl.phasenfristen
            if len(fristen) < nr or fristen[nr - 1] != tag:
                fehler.append(f"„{vorher['terminart']}“ gesetzt, aber Fristen sind "
                              f"{[f'{f:%d.%m.}' for f in fristen]}")
    elif art == "semester":
        semester = sg.semester_von(modul)
        ist = semester.nummer if semester else 0
        if ist != werte[0]:
            fehler.append(f"Modul liegt im Semester {ist} statt {werte[0]}")
    return fehler


def stichtage_fuer(sg: Studiengang) -> list[date]:
    beginn = sg.startdatum
    ende = sg.semester_liste[-1].ende if sg.semester_liste else beginn
    return [beginn - timedelta(days=30), beginn, beginn + timedelta(days=1), STICHTAG,
            sg.semester_liste[0].ende if sg.semester_liste else beginn,
            ende, ende + timedelta(days=1), ende + timedelta(days=3650)]


def anzeige_pruefen(sg: Studiengang, stichtag: date) -> list[tuple[str, str]]:
    """Baut die Anzeige auf und prüft die Kennzahlen auf ihre Grenzen."""
    fehler = []
    try:
        controller = controller_fuer(sg, stichtag)
        daten = controller.dashboard_daten()
        erfassbar = controller.erfassbare_module()
    except Exception as e:                                # noqa: BLE001
        return [("Absturz Anzeige", f"Stichtag {stichtag}: {type(e).__name__}: {e}")]
    g = daten.ects_gesamt
    if not 0 <= daten.ects_soll_heute <= g:
        fehler.append(("Kennzahl", f"Soll {daten.ects_soll_heute} außerhalb 0..{g}"))
    if daten.ects_bestanden + daten.ects_laufend > sum(m.ects for m in sg.module):
        fehler.append(("Kennzahl", "bestanden + laufend größer als der Katalog"))
    bestanden = [m for m in sg.module if m.ist_bestanden()]
    if len(daten.notenverlauf) != len(bestanden):
        fehler.append(("Notenverlauf", f"{len(daten.notenverlauf)} Punkte bei "
                                       f"{len(bestanden)} bestandenen Modulen"))
    schnitt = sg.notendurchschnitt()
    if daten.notenverlauf and daten.notenverlauf[-1] != schnitt:
        fehler.append(("Notenverlauf", f"letzter Punkt {daten.notenverlauf[-1]} "
                                       f"≠ Durchschnitt {schnitt}"))
    if schnitt is not None and not Decimal("1.0") <= schnitt <= GRENZE:
        fehler.append(("Kennzahl", f"Durchschnitt {schnitt}"))
    for b, l, p in daten.ects_je_semester:
        if min(b, l, p) < 0:
            fehler.append(("Kennzahl", f"negative ECTS je Semester ({b}, {l}, {p})"))
    if len(erfassbar) != len(sg.module):
        fehler.append(("Dialog", "Modulliste im Dialog unvollständig"))
    for m in (*daten.module, *erfassbar):
        treffer = re.match(r"(\d+) von (\d+)", m.phasen)
        if treffer and int(treffer.group(1)) > int(treffer.group(2)):
            fehler.append(("Anzeige", f"{m.kuerzel}: „{m.phasen}“"))
    aktuell = sg.aktuelles_semester(stichtag)
    erwartet = tuple(m.kuerzel for m in aktuell.module) if aktuell else ()
    if tuple(m.kuerzel for m in daten.module) != erwartet:
        fehler.append(("Anzeige", "Bereich F zeigt nicht die Module des aktuellen Semesters"))
    if not daten.hinweis:
        fehler.append(("Hinweis", "Bereich G ist leer"))
    ueberfaellig = [m for m in sg.module if m.pruefungsleistung.naechster_termin()
                    and m.pruefungsleistung.naechster_termin() < stichtag]
    if ueberfaellig and not daten.hinweis.startswith("Frist überschritten"):
        fehler.append(("Hinweis", f"überfällige Frist ({ueberfaellig[0].kuerzel}), "
                                  f"Hinweis lautet „{daten.hinweis}“"))
    notenziel = next((z for z in sg.ziele if isinstance(z, Notenziel)), None)
    if notenziel is not None:
        rest = notenziel.restdurchschnitt(sg)
        offen = g - sum(m.ects for m in bestanden)
        if rest is not None and offen > 0:
            summe = sum((m.note() * m.ects for m in bestanden), Decimal(0))
            ergebnis = (summe + rest * offen) / g
            if abs(ergebnis - notenziel.ziel_durchschnitt) > Decimal("0.01"):
                fehler.append(("Kennzahl", f"Restdurchschnitt {rest} führt zu {ergebnis:.3f}"))
    return fehler


class Rundreise:
    """Speichert in eine SQLite-Datei und lädt wieder; vergleicht Zustand und Anzeige."""

    def __init__(self, ordner: Path) -> None:
        self._repo = SqliteStudiengangRepository(ordner / "rundreise.db")

    def pruefen(self, sg: Studiengang) -> list[tuple[str, str]]:
        try:
            self._repo.speichere(sg)
        except Exception as e:                            # noqa: BLE001
            return [("Speichern", f"{type(e).__name__}: {e}")]
        try:
            geladen = self._repo.lade()
        except Exception as e:                            # noqa: BLE001
            return [("Laden", "gespeicherter Stand lässt sich nicht laden, das Dashboard "
                              f"startet danach nicht mehr: {type(e).__name__}: {e}")]
        if abbild(geladen) != abbild(sg):
            return [("Laden", "geladener Stand weicht vom gespeicherten ab")]
        if controller_fuer(geladen).dashboard_daten() != controller_fuer(sg).dashboard_daten():
            return [("Laden", "Anzeige nach dem Laden anders als vorher")]
        return []


# ====================================================================== Teil: Zustände
@dataclass
class Knoten:
    sg: Studiengang
    folge: tuple
    tiefe: int


def suchmodule(vorlage: Studiengang) -> list[str]:
    """Je ein Modul jeder Prüfungsform und Ausgangslage aus den Beispieldaten."""
    gewaehlt: dict[str, str] = {}
    for m in vorlage.module:
        pl = m.pruefungsleistung
        semester = vorlage.semester_von(m)
        merkmal = (type(pl).__name__, pl.status.value,
                   "fristen" if getattr(pl, "phasenfristen", ()) else "",
                   "mit Semester" if semester else "ohne Semester")
        gewaehlt.setdefault(" ".join(merkmal), m.kuerzel)
    return list(gewaehlt.values())


def teil_zustaende(sammlung: Sammlung, vorlage: Studiengang, tiefe: int, ordner: Path,
                   zeichner) -> None:
    rundreise = Rundreise(ordner)
    gesamt_zustaende = 0
    for kuerzel in suchmodule(vorlage):
        start = auszug(vorlage, kuerzel)
        lage = beschreibe(start, kuerzel)
        schritte = schritte_fuer_suche(start)
        gesehen = {abbild(start): 0}
        kanten: dict[tuple, set[tuple]] = {}
        knoten_von: dict[tuple, Knoten] = {abbild(start): Knoten(start, (), 0)}
        schlange = deque([knoten_von[abbild(start)]])
        t0 = time.perf_counter()
        while schlange:
            knoten = schlange.popleft()
            k_alt = abbild(knoten.sg)
            if knoten.tiefe >= tiefe:
                continue
            for schritt in schritte:
                sg = copy.deepcopy(knoten.sg)
                folge = knoten.folge + (schritt,)
                lesbar = tuple(schritt_text(s) for s in folge)
                vorher = modul_vorher(sg, kuerzel)
                try:
                    ausfuehren(controller_fuer(sg), kuerzel, schritt)
                except ValueError as e:
                    if abbild(sg) != k_alt:
                        sammlung.melde("FEHLER", "zustaende", "Ablehnung ändert Zustand",
                                       f"{e}", lesbar, lage)
                    if not str(e).strip():
                        sammlung.melde("FEHLER", "zustaende", "Ablehnung ohne Meldung",
                                       schritt_text(schritt), lesbar, lage)
                    continue
                except Exception as e:                    # noqa: BLE001
                    sammlung.melde("FEHLER", "zustaende", "Absturz",
                                   f"{type(e).__name__}: {e}", lesbar, lage)
                    continue
                for text in wirkung_pruefen(sg, kuerzel, schritt, vorher):
                    sammlung.melde("FEHLER", "zustaende", "falsche Wirkung", text, lesbar, lage)
                k_neu = abbild(sg)
                kanten.setdefault(k_alt, set()).add(k_neu)
                if k_neu in gesehen:
                    continue
                gesehen[k_neu] = knoten.tiefe + 1
                neu = Knoten(sg, folge, knoten.tiefe + 1)
                knoten_von[k_neu] = neu
                schlange.append(neu)
                for art, text in regeln_pruefen(sg):
                    sammlung.melde("FEHLER", "zustaende", art, text, lesbar, lage)
                for art, text in rundreise.pruefen(sg):
                    sammlung.melde("FEHLER", "zustaende", art, text, lesbar, lage)
                for tag in stichtage_fuer(sg):
                    for art, text in anzeige_pruefen(sg, tag):
                        sammlung.melde("FEHLER", "zustaende", art, text, lesbar, lage)
                if zeichner is not None and len(gesehen) % 25 == 0:
                    zeichner.zeichnen_pruefen(sammlung, "zustaende", sg, lesbar, lage)
        sackgassen_pruefen(sammlung, kuerzel, lage, knoten_von, kanten, gesehen, tiefe)
        gesamt_zustaende += len(gesehen)
        print(f"   {kuerzel:6} {len(gesehen):6} Zustände  {time.perf_counter() - t0:6.1f} s"
              f"   ({lage})")
    print(f"   zusammen {gesamt_zustaende} Zustände")


def ist_endzustand(sg: Studiengang, kuerzel: str) -> bool:
    """Bestanden, oder alle drei Versuche nicht bestanden (gewolltes Ende)."""
    pl = sg.modul(kuerzel).pruefungsleistung
    return pl.ist_bestanden() or (pl.status is Pruefungsstatus.NICHT_BESTANDEN
                                  and pl.versuchsnummer >= MAX_VERSUCHE)


def sackgassen_pruefen(sammlung: Sammlung, kuerzel: str, lage: str, knoten_von: dict,
                       kanten: dict, gesehen: dict, tiefe: int) -> None:
    """Meldet Zustände, aus denen das Modul nicht mehr bestanden werden kann.

    Rückwärts von allen Endzuständen aus wird markiert, wer sie erreicht. Zustände
    am Rand der Suche (wenige Schritte vor der Tiefengrenze) werden nicht
    beurteilt, weil ihr Weg zum Ziel jenseits der Grenze liegen kann.
    """
    rueckwaerts: dict[tuple, set[tuple]] = {}
    for von, nach_menge in kanten.items():
        for nach in nach_menge:
            rueckwaerts.setdefault(nach, set()).add(von)
    gut = {k for k, kn in knoten_von.items() if ist_endzustand(kn.sg, kuerzel)}
    arbeit = list(gut)
    while arbeit:
        k = arbeit.pop()
        for vorgaenger in rueckwaerts.get(k, ()):
            if vorgaenger not in gut:
                gut.add(vorgaenger)
                arbeit.append(vorgaenger)
    # So viele Schritte braucht der längste Weg zum Bestehen: Semester zuordnen,
    # Termin, anmelden, Note; beim Portfolio drei Fristen und drei Phasen.
    pl = next(iter(knoten_von.values())).sg.modul(kuerzel).pruefungsleistung
    rand = 3 + 2 * PHASEN_JE_PORTFOLIO if isinstance(pl, Portfolio) else 6
    for k, kn in knoten_von.items():
        if k in gut or gesehen[k] > tiefe - rand:
            continue
        sammlung.melde("FEHLER", "zustaende", "Sackgasse",
                       f"Modul kann nicht mehr bestanden werden ({beschreibe(kn.sg, kuerzel)})",
                       tuple(schritt_text(s) for s in kn.folge), lage)


# ====================================================================== Teil: Zufall
def spiele(folge: list[tuple], stichtag: date = STICHTAG, rundreise: Rundreise | None = None,
           pruefe_anzeige: bool = True) -> tuple[str, str] | None:
    """Spielt eine Folge (kuerzel, schritt) ab und liefert den ersten Fehler oder None."""
    sg = lade_beispiel()
    for nr, (kuerzel, schritt) in enumerate(folge, start=1):
        vorher_abbild = abbild(sg)
        vorher = modul_vorher(sg, kuerzel)
        try:
            ausfuehren(controller_fuer(sg, stichtag), kuerzel, schritt)
        except ValueError:
            if abbild(sg) != vorher_abbild:
                return ("Ablehnung ändert Zustand", schritt_text(schritt))
            continue
        except Exception as e:                            # noqa: BLE001
            return ("Absturz", f"{type(e).__name__}: {e}")
        for text in wirkung_pruefen(sg, kuerzel, schritt, vorher):
            return ("falsche Wirkung", text)
        for art, text in regeln_pruefen(sg, stichtag):
            return (art, text)
        if pruefe_anzeige:
            for tag in (stichtag, stichtag + timedelta(days=400)):
                for art, text in anzeige_pruefen(sg, tag):
                    return (art, text)
        if rundreise is not None and (nr % 5 == 0 or nr == len(folge)):
            for art, text in rundreise.pruefen(sg):
                return (art, text)
    return None


def kuerzen(folge: list[tuple], fehler: tuple[str, str], ordner: Path) -> list[tuple]:
    """Entfernt Schritte, solange derselbe Fehler (gleiche Art) auftritt."""
    rundreise = Rundreise(ordner)
    art = fehler[0]
    geaendert = True
    while geaendert:
        geaendert = False
        for i in range(len(folge) - 1, -1, -1):
            kuerzer = folge[:i] + folge[i + 1:]
            ergebnis = spiele(kuerzer, rundreise=rundreise)
            if ergebnis is not None and ergebnis[0] == art:
                folge = kuerzer
                geaendert = True
    return folge


def teil_zufall(sammlung: Sammlung, vorlage: Studiengang, laeufe: int, laenge: int,
                startwert: int, ordner: Path) -> None:
    zufall = random.Random(startwert)
    rundreise = Rundreise(ordner)
    alle = [m.kuerzel for m in vorlage.module]
    t0 = time.perf_counter()
    gefunden = 0
    for lauf in range(laeufe):
        # Wenige Module je Lauf, damit lange Folgen am selben Modul entstehen;
        # dazu ab und zu ein beliebiges.
        auswahl = zufall.sample(alle, zufall.randint(1, 4))
        folge = []
        for _ in range(laenge):
            kuerzel = zufall.choice(auswahl) if zufall.random() < 0.9 else zufall.choice(alle)
            folge.append((kuerzel, zufallsschritt(zufall, vorlage)))
        fehler = spiele(folge, rundreise=rundreise)
        if fehler is not None:
            gefunden += 1
            kurz = kuerzen(folge, fehler, ordner)
            ergebnis = spiele(kurz, rundreise=Rundreise(ordner)) or fehler
            sg = lade_beispiel()
            lesbar = tuple(f"{k}: {schritt_text(s)}" for k, s in kurz)
            lage = "; ".join(sorted({beschreibe(sg, k) for k, _ in kurz}))
            sammlung.melde("FEHLER", "zufall", ergebnis[0], ergebnis[1], lesbar,
                           f"Beispieldaten, Stichtag {STICHTAG:%d.%m.%Y}; {lage}")
        if (lauf + 1) % max(1, laeufe // 10) == 0:
            print(f"   {lauf + 1:5}/{laeufe} Läufe, {gefunden} mit Fehler, "
                  f"{time.perf_counter() - t0:6.1f} s")


# ====================================================================== Teil: Stichtage
def teil_stichtage(sammlung: Sammlung, vorlage: Studiengang) -> None:
    """Anzeige der Beispieldaten für jeden Tag vom Monat vor Studienbeginn bis lange danach."""
    beginn = vorlage.startdatum - timedelta(days=40)
    ende = vorlage.semester_liste[-1].ende + timedelta(days=400)
    tag, anzahl = beginn, 0
    while tag <= ende:
        for art, text in anzeige_pruefen(vorlage, tag):
            sammlung.melde("FEHLER", "stichtage", art, text, (f"Stichtag {tag:%d.%m.%Y}",),
                           "Beispieldaten unverändert")
        tag += timedelta(days=1)
        anzahl += 1
    for tag in (date(2099, 12, 31), date(1990, 1, 1)):
        for art, text in anzeige_pruefen(vorlage, tag):
            sammlung.melde("FEHLER", "stichtage", art, text, (f"Stichtag {tag:%d.%m.%Y}",),
                           "Beispieldaten unverändert")
        anzahl += 1
    # Leeres Studium: kein Modul bewertet, nichts angemeldet
    leer = Studiengang("Leer", Abschlussgrad.BACHELOR_OF_SCIENCE, vorlage.startdatum)
    for _ in range(6):
        leer.neues_semester()
    for ziel in vorlage.ziele:
        leer.neues_ziel(copy.deepcopy(ziel))
    for tag in stichtage_fuer(leer):
        for art, text in anzeige_pruefen(leer, tag):
            sammlung.melde("FEHLER", "stichtage", art, text, (f"Stichtag {tag:%d.%m.%Y}",),
                           "Studiengang ohne Module")
    print(f"   {anzahl} Stichtage")


# ====================================================================== Teil: Kalender
def teil_kalender(sammlung: Sammlung, gruendlich: bool) -> None:
    """Semestergrenzen und Sollwert für viele Studienbeginne."""
    starts = set()
    for jahr in range(2023, 2031):
        for monat in range(1, 13):
            for tag in (1, 15, 28, 29, 30, 31):
                try:
                    starts.add(date(jahr, monat, tag))
                except ValueError:
                    pass
    if gruendlich:
        tag = date(2024, 1, 1)
        while tag < date(2029, 1, 1):
            starts.add(tag)
            tag += timedelta(days=1)
    for start in sorted(starts):
        folge = (f"Studienbeginn {start:%d.%m.%Y}",)
        sg = Studiengang("Test", Abschlussgrad.BACHELOR_OF_SCIENCE, start)
        for _ in range(6):
            sg.neues_semester()
        liste = sg.semester_liste
        if liste[0].beginn != start:
            sammlung.melde("FEHLER", "kalender", "Semester", "1. Semester beginnt nicht am "
                           "Studienbeginn", folge)
        for a, b in zip(liste, liste[1:]):
            if b.beginn != a.ende + timedelta(days=1):
                sammlung.melde("FEHLER", "kalender", "Semester",
                               f"Lücke/Überlappung zwischen {a.nummer}. und {b.nummer}. Semester "
                               f"({a.ende} / {b.beginn})", folge)
        for s in liste:
            dauer = (s.ende - s.beginn).days + 1
            if not 181 <= dauer <= 185:
                sammlung.melde("FEHLER", "kalender", "Semester",
                               f"{s.nummer}. Semester dauert {dauer} Tage", folge)
        vorher = Decimal(-1)
        tag = start - timedelta(days=3)
        ende = liste[-1].ende + timedelta(days=3)
        while tag <= ende:
            soll = sg.soll_ects(tag)
            if soll < vorher:
                sammlung.melde("FEHLER", "kalender", "Sollwert",
                               f"Sollwert sinkt am {tag} ({vorher} -> {soll})", folge)
            if not 0 <= soll <= 180:
                sammlung.melde("FEHLER", "kalender", "Sollwert", f"Soll {soll} am {tag}", folge)
            aktuell = sg.aktuelles_semester(tag)
            drin = [s.nummer for s in liste if s.enthaelt(tag)]
            if (start <= tag <= liste[-1].ende) != (aktuell is not None) or len(drin) > 1:
                sammlung.melde("FEHLER", "kalender", "aktuelles Semester",
                               f"am {tag}: {drin}", folge)
            vorher = soll
            tag += timedelta(days=1 if gruendlich else 3)
        danach = sg.soll_ects(liste[-1].ende + timedelta(days=1))
        if danach != 180:
            sammlung.melde("FEHLER", "kalender", "Sollwert",
                           f"nach der Regelstudienzeit Soll {danach} statt 180", folge)
        for nr in range(1, 7):
            if sg.verstrichene_semester(sg.semesterbeginn(nr)) != nr - 1:
                sammlung.melde("FEHLER", "kalender", "Sollwert",
                               f"am Beginn des {nr}. Semesters verstrichen "
                               f"{sg.verstrichene_semester(sg.semesterbeginn(nr))}", folge)
    # Monatsarithmetik direkt
    for tag in (date(2028, 2, 29), date(2027, 8, 31), date(2026, 3, 31), date(2026, 12, 31)):
        for monate in range(0, 48):
            try:
                _plus_monate(tag, monate)
            except Exception as e:                        # noqa: BLE001
                sammlung.melde("FEHLER", "kalender", "Monatsrechnung",
                               f"{tag} + {monate} Monate: {type(e).__name__}: {e}")
    print(f"   {len(starts)} Studienbeginne")


# ====================================================================== Teil: Datenbank
def teil_datenbank(sammlung: Sammlung, ordner: Path) -> None:
    datei = ordner / "studium.db"
    shutil.copyfile(BEISPIEL_DB, datei)

    # 1. Fehler mitten im Speichern: Datei behält den alten Stand, Anzeige auch.
    repo = SqliteStudiengangRepository(datei)
    c = DashboardController(repo, KennzahlenService(), ErfassungsService(), STICHTAG)
    vorher = abbild(repo.lade())
    original = SqliteStudiengangRepository.__dict__["_speichere_ziel"]    # staticmethod

    def kaputt(*_a, **_k):
        raise sqlite3.OperationalError("simulierter Fehler beim Schreiben")
    SqliteStudiengangRepository._speichere_ziel = staticmethod(kaputt)
    try:
        c.status_setzen("P2-01", Pruefungsstatus.ANGEMELDET)
        sammlung.melde("FEHLER", "datenbank", "Speicherfehler",
                       "Fehler beim Speichern wurde nicht gemeldet")
    except sqlite3.OperationalError:
        pass
    finally:
        SqliteStudiengangRepository._speichere_ziel = original
    if abbild(repo.lade()) != vorher:
        sammlung.melde("FEHLER", "datenbank", "Speicherfehler",
                       "halb gespeicherter Stand in der Datei (keine Transaktion)")
    if abbild(c._studiengang) != vorher:
        sammlung.melde("FEHLER", "datenbank", "Speicherfehler",
                       "Anzeige zeigt nach gescheitertem Speichern den ungespeicherten Stand")

    # 2. Zwei Dashboards gleichzeitig auf derselben Datei (zweimal doppelgeklickt)
    shutil.copyfile(BEISPIEL_DB, datei)
    a = DashboardController(SqliteStudiengangRepository(datei), KennzahlenService(),
                            ErfassungsService(), STICHTAG)
    b = DashboardController(SqliteStudiengangRepository(datei), KennzahlenService(),
                            ErfassungsService(), STICHTAG)
    a.status_setzen("P2-01", Pruefungsstatus.ANGEMELDET)
    b.status_setzen("P2-02", Pruefungsstatus.ANGEMELDET)
    geladen = SqliteStudiengangRepository(datei).lade()
    if geladen.modul("P2-01").pruefungsleistung.status is not Pruefungsstatus.ANGEMELDET:
        sammlung.melde("HINWEIS", "datenbank", "zwei Fenster",
                       "Sind zwei Dashboards gleichzeitig offen, überschreibt das zweite beim "
                       "Speichern die Eingaben des ersten ohne Warnung",
                       ("Dashboard zweimal starten", "im ersten P2-01 anmelden",
                        "im zweiten P2-02 anmelden", "neu starten: P2-01 ist wieder geplant"))

    # 3. Von Hand veränderte Datenbank: Laden muss mit verständlicher Meldung abbrechen
    faelle = {
        "Note 2,2": "UPDATE pruefungsleistung SET note='2.2' WHERE note IS NOT NULL",
        "unbekannter Status": "UPDATE pruefungsleistung SET status='xyz' WHERE modul_id=1",
        "kaputtes Datum": "UPDATE pruefungsleistung SET bewertet_am='31.12.' "
                          "WHERE bewertet_am IS NOT NULL",
        "Phasen > Fristen": "UPDATE pruefungsleistung SET abgegebene_phasen=9 "
                            "WHERE art='portfolio'",
        "leere Datenbank": "DELETE FROM studiengang",
    }
    for name, sql in faelle.items():
        shutil.copyfile(BEISPIEL_DB, datei)
        with sqlite3.connect(datei) as v:
            v.execute("PRAGMA foreign_keys = ON")
            v.execute(sql)
        v.close()
        try:
            SqliteStudiengangRepository(datei).lade()
            sammlung.melde("HINWEIS", "datenbank", "Prüfung beim Laden",
                           f"veränderte Datenbank ({name}) wird ohne Meldung geladen")
        except (ValueError, LookupError):
            pass
        except Exception as e:                            # noqa: BLE001
            sammlung.melde("HINWEIS", "datenbank", "Prüfung beim Laden",
                           f"{name}: unerwartete Fehlerart {type(e).__name__}: {e}")
    print("   Speicherfehler, zwei Fenster, veränderte Datenbank geprüft")


# ====================================================================== Teil: Oberfläche
class Zeichner:
    """Echte tkinter-Fenster für die Prüfung der Darstellung."""

    def __init__(self) -> None:
        import tkinter as tk
        from ui.dashboard_view import DashboardView
        self.tk = tk
        self.View = DashboardView
        self.wurzel = tk.Tk()
        self.wurzel.withdraw()
        self.ausnahmen: list[BaseException] = []
        self.wurzel.report_callback_exception = lambda *info: self.ausnahmen.append(info[1])

    def schliessen(self) -> None:
        try:
            self.wurzel.destroy()
        except Exception:                                 # noqa: BLE001
            pass

    def _texte(self, canvas) -> list[tuple[str, tuple[int, int, int, int]]]:
        return [(canvas.itemcget(i, "text"), canvas.bbox(i))
                for i in canvas.find_all() if canvas.type(i) == "text"]

    def zeichnen_pruefen(self, sammlung: Sammlung, teil: str, sg: Studiengang,
                         folge: tuple[str, ...], lage: str,
                         stichtage: tuple[date, ...] = (STICHTAG,)) -> None:
        for stichtag in stichtage:
            fenster = self.tk.Toplevel(self.wurzel)
            try:
                view = self.View(fenster, controller_fuer(copy.deepcopy(sg), stichtag))
                for groesse in ("1040x690", "1500x950"):
                    fenster.geometry(groesse)
                    fenster.update()
                    canvas = view._canvas
                    self._pruefe_canvas(sammlung, teil, canvas, folge,
                                        f"{lage}; Stichtag {stichtag:%d.%m.%Y}, Fenster {groesse}")
            except Exception as e:                        # noqa: BLE001
                sammlung.melde("FEHLER", teil, "Absturz Zeichnen", f"{type(e).__name__}: {e}",
                               folge, lage)
            finally:
                fenster.destroy()
            self._ausnahmen_melden(sammlung, teil, folge, lage)

    def _pruefe_canvas(self, sammlung, teil, canvas, folge, lage) -> None:
        breite, hoehe = canvas.winfo_width(), canvas.winfo_height()
        texte = [(t, b) for t, b in self._texte(canvas) if t.strip() and b]
        for text, (x0, y0, x1, y1) in texte:
            if x0 < -1 or x1 > breite + 1 or y1 > hoehe + 1:
                sammlung.melde("HINWEIS", teil, "Text ragt aus dem Fenster",
                               f"„{text[:60]}“", folge, lage)
        for i, (t1, a) in enumerate(texte):
            for t2, b in texte[i + 1:]:
                breite_ueber = min(a[2], b[2]) - max(a[0], b[0])
                hoehe_ueber = min(a[3], b[3]) - max(a[1], b[1])
                if breite_ueber > 3 and hoehe_ueber > 3:
                    kleiner = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
                    if breite_ueber * hoehe_ueber > 0.15 * kleiner:
                        sammlung.melde("HINWEIS", teil, "Texte überlappen",
                                       f"„{t1[:40]}“ und „{t2[:40]}“", folge, lage)

    def _ausnahmen_melden(self, sammlung, teil, folge, lage) -> None:
        for fehler in self.ausnahmen:
            text = "".join(traceback.format_exception_only(type(fehler), fehler)).strip()
            sammlung.melde("FEHLER", teil, "Ausnahme in der Oberfläche", text, folge, lage)
        self.ausnahmen.clear()


DATUMSEINGABEN = ("10.10.2026", "11.10.2026", "09.08.2026", "10.08.2026", "30.10.2026",
                  "01.04.2027", "31.12.2030", "29.02.2028", "29.02.2027", "31.04.2027",
                  "1.1.2027", "2026-10-10", "", "  10.10.2026  ", "abc", "10.10.26")


def teil_oberflaeche(sammlung: Sammlung, zeichner: Zeichner, schritte: int, startwert: int,
                     ordner: Path) -> None:
    """Zufällige Bedienung des echten Dialogs: Auswahlfelder, Datumsfeld, Knöpfe."""
    zufall = random.Random(startwert)
    vorlage = lade_beispiel()

    # 1. Dashboard für jeden Monat der Regelstudienzeit in zwei Größen zeichnen
    tag = vorlage.startdatum - timedelta(days=10)
    stichtage = []
    while tag < vorlage.semester_liste[-1].ende + timedelta(days=60):
        stichtage.append(tag)
        tag += timedelta(days=30)
    zeichner.zeichnen_pruefen(sammlung, "oberflaeche", vorlage, ("unveränderte Beispieldaten",),
                              "Beispieldaten", tuple(stichtage))

    # 2. Zufallsbedienung über die echten Widgets, gespeichert in SQLite
    datei = ordner / "oberflaeche.db"
    shutil.copyfile(BEISPIEL_DB, datei)
    repo = SqliteStudiengangRepository(datei)
    controller = DashboardController(repo, KennzahlenService(), ErfassungsService(), STICHTAG)
    fenster = zeichner.tk.Toplevel(zeichner.wurzel)
    view = zeichner.View(fenster, controller)
    view._oeffne_erfassung()
    dialog = view._dialog
    protokoll: list[str] = []
    knoepfe = {
        "Note eintragen": lambda: dialog._note_knopf,
        "Note entfernen": lambda: dialog._entfernen_knopf,
        "Termin setzen": lambda: dialog._termin_knopf,
        "Status setzen": lambda: dialog._status_knopf,
        "Phase abgeben": lambda: dialog._phase,
        "Zuordnen": lambda: dialog._zuordnen_knopf,
    }
    try:
        for nr in range(1, schritte + 1):
            if not dialog.ist_offen():
                view._oeffne_erfassung()
                dialog = view._dialog
                protokoll.append("Dialog neu geöffnet")
            wahl = zufall.random()
            if wahl < 0.25:
                anzahl = len(dialog._module)
                # meist wenige Module, damit lange Folgen am selben Modul entstehen
                index = zufall.randrange(min(anzahl, 8)) if zufall.random() < 0.8 \
                    else zufall.randrange(anzahl)
                dialog._auswahl.current(index)
                dialog._auswahl.event_generate("<<ComboboxSelected>>")
                protokoll.append(f"Modul wählen: {dialog._module[index].bezeichnung}")
            elif wahl < 0.35:
                text = zufall.choice(DATUMSEINGABEN)
                dialog._datum.delete(0, "end")
                dialog._datum.insert(0, text)
                protokoll.append(f"Datum eingeben: „{text}“")
            elif wahl < 0.45:
                i = zufall.randrange(len(dialog._noten))
                dialog._note.current(i)
                protokoll.append(f"Note wählen: {dialog._note.get()}")
            elif wahl < 0.52:
                i = zufall.randrange(len(dialog._status_werte))
                dialog._status.current(i)
                protokoll.append(f"Status wählen: {dialog._status.get()}")
            elif wahl < 0.58:
                i = zufall.randrange(len(dialog._semester_werte))
                dialog._semester.current(i)
                protokoll.append(f"Semester wählen: {dialog._semester.get()}")
            elif wahl < 0.995:
                name = zufall.choice(sorted(knoepfe))
                knopf = knoepfe[name]()
                vorher_db = abbild(repo.lade())
                gesperrt = "disabled" in knopf.state()
                knopf.invoke()
                protokoll.append(f"Knopf „{name}“" + (" (ausgegraut)" if gesperrt else ""))
                meldung = str(dialog._meldung["text"])
                if gesperrt and abbild(repo.lade()) != vorher_db:
                    sammlung.melde("FEHLER", "oberflaeche", "ausgegrauter Knopf",
                                   f"„{name}“ hat trotz Sperre gespeichert", tuple(protokoll))
                if not gesperrt and not meldung:
                    sammlung.melde("FEHLER", "oberflaeche", "keine Rückmeldung",
                                   f"„{name}“ zeigt keine Meldung", tuple(protokoll))
                if meldung.startswith("Speichern fehlgeschlagen"):
                    sammlung.melde("FEHLER", "oberflaeche", "Speichern fehlgeschlagen",
                                   meldung, tuple(protokoll))
                protokoll.append(f"   Meldung: {meldung}")
            else:
                dialog._fenster.destroy()
                protokoll.append("Dialog geschlossen")
            fenster.update()
            if zufall.random() < 0.05:
                groesse = zufall.choice(("1040x690", "1200x800", "1700x1000"))
                fenster.geometry(groesse)
                fenster.update()
                protokoll.append(f"Fenstergröße {groesse}")
            zeichner._ausnahmen_melden(sammlung, "oberflaeche", tuple(protokoll), "Beispieldaten")
            # Anzeige, Dialog und Datei müssen zum selben Stand passen
            sg = controller._studiengang
            if abbild(repo.lade()) != abbild(sg):
                sammlung.melde("FEHLER", "oberflaeche", "Datei ≠ Anzeige",
                               "gespeicherter Stand weicht vom angezeigten ab", tuple(protokoll))
            if view._daten != controller.dashboard_daten():
                sammlung.melde("FEHLER", "oberflaeche", "Anzeige veraltet",
                               "Dashboard zeigt nach einer Änderung den alten Stand",
                               tuple(protokoll))
            if dialog.ist_offen() and dialog._module != controller.erfassbare_module():
                sammlung.melde("FEHLER", "oberflaeche", "Dialog veraltet",
                               "Modulliste im Dialog zeigt nicht den aktuellen Stand",
                               tuple(protokoll))
            for art, text in regeln_pruefen(sg):
                sammlung.melde("FEHLER", "oberflaeche", art, text, tuple(protokoll))
            if nr % 100 == 0:
                zeichner._pruefe_canvas(sammlung, "oberflaeche", view._canvas, tuple(protokoll),
                                        "Beispieldaten nach Zufallsbedienung")
                print(f"   {nr:5}/{schritte} Bedienschritte")
            if len(protokoll) > 400:              # nur die letzten Schritte aufheben
                protokoll = protokoll[-400:]
    finally:
        fenster.destroy()


# ====================================================================== Bericht
def bericht(sammlung: Sammlung, dauer: float, umfang: str) -> str:
    zeilen = [f"Tiefentest ({umfang}), Dauer {dauer:.0f} s",
              f"{sammlung.anzahl('FEHLER')} Fehler, {sammlung.anzahl('HINWEIS')} Hinweise", ""]
    reihenfolge = sorted(sammlung.befunde.values(),
                         key=lambda b: (b.schwere != "FEHLER", b.teil, b.art, len(b.folge)))
    for nr, b in enumerate(reihenfolge, start=1):
        zeilen.append(f"[{nr}] {b.schwere} · {b.teil} · {b.art} · {b.anzahl}× gefunden")
        zeilen.append(f"    {b.text}")
        if b.ausgangslage:
            zeilen.append(f"    Ausgangslage: {b.ausgangslage}")
        if b.folge:
            zeilen.append("    Kürzeste Folge:")
            zeilen += [f"      {i}. {s}" for i, s in enumerate(b.folge[-40:], start=1)]
        zeilen.append("")
    if not sammlung.befunde:
        zeilen.append("Keine Befunde.")
    return "\n".join(zeilen)


def main(argumente: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tiefentest des Studien-Dashboards")
    stufe = parser.add_mutually_exclusive_group()
    stufe.add_argument("--schnell", action="store_true", help="kleiner Umfang")
    stufe.add_argument("--gruendlich", action="store_true", help="großer Umfang")
    parser.add_argument("--nur", default="",
                        help="Teile mit Komma: zustaende,zufall,stichtage,kalender,"
                             "datenbank,oberflaeche")
    parser.add_argument("--tiefe", type=int, help="maximale Folgenlänge der Zustandssuche")
    parser.add_argument("--laeufe", type=int, help="Anzahl zufälliger Folgen")
    parser.add_argument("--laenge", type=int, help="Länge jeder zufälligen Folge")
    parser.add_argument("--startwert", type=int, default=20261011,
                        help="Startwert des Zufalls (gleicher Wert = gleiche Folgen)")
    parser.add_argument("--bericht", type=Path, help="Bericht zusätzlich in diese Datei schreiben")
    parser.add_argument("--ohne-fenster", action="store_true",
                        help="keine tkinter-Fenster öffnen (Darstellung wird nicht geprüft)")
    args = parser.parse_args(argumente)

    umfang = "schnell" if args.schnell else "gruendlich" if args.gruendlich else "standard"
    tiefe, laeufe, laenge, dialogschritte = UMFANG[umfang]
    tiefe = args.tiefe or tiefe
    laeufe = args.laeufe or laeufe
    laenge = args.laenge or laenge
    alle = ["zustaende", "zufall", "stichtage", "kalender", "datenbank", "oberflaeche"]
    teile = [t.strip() for t in args.nur.split(",") if t.strip()] or alle
    unbekannt = set(teile) - set(alle)
    if unbekannt:
        parser.error(f"unbekannte Teile: {', '.join(sorted(unbekannt))}")

    zeichner = None
    if args.ohne_fenster:
        teile = [t for t in teile if t != "oberflaeche"]
    elif "oberflaeche" in teile or "zustaende" in teile:
        try:
            zeichner = Zeichner()
        except Exception as e:                            # noqa: BLE001
            print(f"Hinweis: Oberfläche nicht verfügbar ({e}); Teil oberflaeche entfällt.")
            teile = [t for t in teile if t != "oberflaeche"]

    sammlung = Sammlung()
    vorlage = lade_beispiel()
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        ordner = Path(tmp)
        for teil in teile:
            print(f"== {teil}")
            start = time.perf_counter()
            try:
                if teil == "zustaende":
                    teil_zustaende(sammlung, vorlage, tiefe, ordner, zeichner)
                elif teil == "zufall":
                    teil_zufall(sammlung, vorlage, laeufe, laenge, args.startwert, ordner)
                elif teil == "stichtage":
                    teil_stichtage(sammlung, vorlage)
                elif teil == "kalender":
                    teil_kalender(sammlung, umfang == "gruendlich")
                elif teil == "datenbank":
                    teil_datenbank(sammlung, ordner)
                elif teil == "oberflaeche":
                    teil_oberflaeche(sammlung, zeichner, dialogschritte, args.startwert, ordner)
            except Exception as e:                        # noqa: BLE001
                sammlung.melde("FEHLER", teil, "Abbruch des Testteils",
                               "".join(traceback.format_exception(type(e), e,
                                                                  e.__traceback__))[-1500:])
            print(f"   fertig in {time.perf_counter() - start:.1f} s, bisher "
                  f"{sammlung.anzahl('FEHLER')} Fehler, {sammlung.anzahl('HINWEIS')} Hinweise")
    if zeichner is not None:
        zeichner.schliessen()

    text = bericht(sammlung, time.perf_counter() - t0, umfang)
    print()
    print(text)
    if args.bericht:
        args.bericht.write_text(text + "\n", encoding="utf-8")
        print(f"Bericht gespeichert: {args.bericht}")
    return 1 if sammlung.anzahl("FEHLER") else 0


if __name__ == "__main__":
    sys.exit(main())
