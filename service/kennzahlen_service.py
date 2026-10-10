"""Kennzahlen, die keinem einzelnen Domain-Objekt gehören.

Der Sollwert wird hier nicht berechnet; er stammt allein aus
Studiengang.soll_ects() (eine Regel an einer Stelle, Phase 2, Abschnitt 1.6).
Alle Werte entstehen bei jedem Aufruf neu aus den Daten; gespeichert wird
keine Kennzahl, weil sich mehrere Werte mit dem Datum ändern.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from domain import Ampel, Modul, Pruefungsstatus, Studiengang

#: Termine innerhalb dieser Frist meldet Bereich G als nächste Handlung.
VORLAUF_TAGE = 30

#: In Bearbeitung: Die Prüfung ist begonnen, die Note fehlt noch.
LAUFENDE_STATUS = (Pruefungsstatus.ANGEMELDET, Pruefungsstatus.ABGEGEBEN)


def datum_text(tag: date) -> str:
    """Datum in deutscher Schreibweise, z. B. 05.02.2027."""
    return tag.strftime("%d.%m.%Y")


def _tage_text(tage: int) -> str:
    if tage == 0:
        return "heute"
    return "noch 1 Tag" if tage == 1 else f"noch {tage} Tage"


class KennzahlenService:
    """Berechnet die Werte der Bereiche C bis G aus dem Studiengang.

    Die Methoden ändern nichts und speichern nichts; derselbe Studiengang
    und derselbe Stichtag ergeben immer dieselben Werte.
    """

    def laufende_ects(self, sg: Studiengang) -> int:
        """ECTS in Bearbeitung: angemeldet oder abgegeben, aber noch nicht bewertet."""
        return sum(m.ects for m in sg.module
                   if m.pruefungsleistung.status in LAUFENDE_STATUS)

    def ects_je_semester(self, sg: Studiengang) -> list[tuple[int, int, int]]:
        """(bestanden, laufend, geplant) je Semester für Bereich E.

        Geplant ist alles, was dem Semester zugeordnet, aber weder bestanden
        noch angemeldet oder abgegeben ist.
        """
        ergebnis = []
        for semester in sg.semester_liste:
            bestanden = sum(m.ects for m in semester.module if m.ist_bestanden())
            laufend = sum(m.ects for m in semester.module
                          if m.pruefungsleistung.status in LAUFENDE_STATUS)
            ergebnis.append((bestanden, laufend,
                             semester.zugeordnete_ects() - bestanden - laufend))
        return ergebnis

    def notenverlauf(self, sg: Studiengang) -> list[Decimal]:
        """Durchschnitt nach jeder Bewertung, in der Reihenfolge der Bewertungen.

        Sortiert wird nach dem Bewertungsdatum (F5); geplante Termine legen
        die Reihenfolge der Bewertungen nicht fest.
        """
        bewertet = sorted((m for m in sg.module if m.ist_bestanden()),
                          key=lambda m: m.pruefungsleistung.bewertet_am)
        verlauf, summe, gewicht = [], Decimal(0), 0
        for modul in bewertet:
            summe += modul.note() * modul.ects
            gewicht += modul.ects
            verlauf.append((summe / gewicht).quantize(Decimal("0.01"),
                                                      rounding=ROUND_HALF_UP))
        return verlauf

    def ausstehende_bewertungen(self, sg: Studiengang) -> list[Modul]:
        """Abgegebene Module ohne Note; Bereich G nennt sie zusätzlich."""
        return [m for m in sg.module
                if m.pruefungsleistung.status is Pruefungsstatus.ABGEGEBEN]

    def handlungshinweis(self, sg: Studiengang, stichtag: date) -> str:
        """Regelkette für Bereich G; die erste zutreffende Regel greift.

        1. überschrittene Frist  2. ein Ziel im roten Bereich
        3. ein Termin innerhalb von 30 Tagen  4. ein Ziel im gelben Bereich
        """
        termine = sorted(
            ((m.pruefungsleistung.naechster_termin(), m) for m in sg.module
             if m.pruefungsleistung.naechster_termin() is not None),
            key=lambda paar: (paar[0], paar[1].kuerzel))
        aktive_ziele = [z for z in sg.ziele if z.ist_aktiv]
        ampeln = [(z, z.ampelstatus(sg, stichtag)) for z in aktive_ziele]

        ueberfaellig = [(t, m) for t, m in termine if t < stichtag]
        if ueberfaellig:
            termin, modul = ueberfaellig[0]
            return (f"Frist überschritten: «{modul.bezeichnung}» "
                    f"({modul.pruefungsleistung.naechste_aufgabe()}) war am "
                    f"{datum_text(termin)} fällig. Status oder Note eintragen.")

        for ziel, ampel in ampeln:
            if ampel is Ampel.ROT:
                return f"Ziel «{ziel.bezeichnung}» ist rot. Studienplanung prüfen."

        bald = [(t, m) for t, m in termine if (t - stichtag).days <= VORLAUF_TAGE]
        if bald:
            termin, modul = bald[0]
            pl = modul.pruefungsleistung
            tage = _tage_text((termin - stichtag).days)
            if pl.ist_selbst_geplant():
                return (f"«{modul.bezeichnung}»: {pl.naechste_aufgabe()}, selbst geplant "
                        f"zum {datum_text(termin)} ({tage}), Termin noch nicht gebucht.")
            return (f"«{modul.bezeichnung}»: {pl.naechste_aufgabe()} bis "
                    f"{datum_text(termin)} ({tage}).")

        for ziel, ampel in ampeln:
            if ampel is Ampel.GELB:
                return f"Ziel «{ziel.bezeichnung}» ist gelb. Knapp an der Toleranz."

        return "Derzeit steht nichts an."
