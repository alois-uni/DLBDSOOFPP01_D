"""Transportobjekte zwischen Controller und Oberfläche.

Unveränderliche Dataclasses (frozen=True). Folgen sind Tupel, weil frozen=True
eine enthaltene Liste nicht vor Änderungen schützt und ein frozenset
Reihenfolge und doppelte Werte verlöre (Phase 2, Abschnitt 2.1).
Die DTOs enthalten genau die Daten der Skizzenbereiche A bis G; die
Aufzählungen Ampel und Pruefungsstatus gehen unverändert durch, damit die
Oberfläche Farben aus geprüften Werten ableitet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from domain import Ampel, Pruefungsstatus


@dataclass(frozen=True)
class ZielDTO:
    """Kachel A oder B."""
    titel: str
    wert: str
    aussage: str
    ampel: Ampel


@dataclass(frozen=True)
class ModulDTO:
    """Eine Zeile in Bereich F bzw. ein Eintrag im Erfassungsdialog."""
    kuerzel: str
    bezeichnung: str
    ects: int
    pruefungsform: str
    status: Pruefungsstatus
    note: Decimal | None
    naechster_termin: date | None
    semester: int | None = None          # für den Erfassungsdialog
    ist_portfolio: bool = False          # Dialog zeigt "Phase abgeben" nur hier
    phasen: str = ""                     # z. B. "2 von 3 Phasen abgegeben"
    bewertet_am: date | None = None      # für Korrekturen im Dialog
    terminart: str = ""                  # z. B. "Prüfungstermin", "Frist Phase 3"
    versuch: int = 1                     # laufender Prüfungsversuch
    max_versuche: int = 3


@dataclass(frozen=True)
class DashboardDTO:
    """Alles, was die Oberfläche für einen Neuaufbau des Dashboards braucht.

    Die Werte sind fertig berechnet; die Oberfläche rechnet nur noch
    Pixelpositionen aus.
    """

    kopfzeile: str
    stichtag: date
    ziele: tuple[ZielDTO, ...]
    ects_bestanden: int
    ects_laufend: int
    ects_soll_heute: Decimal
    ects_je_semester: tuple[tuple[int, int, int], ...]  # (bestanden, laufend, geplant)
    notenverlauf: tuple[Decimal, ...]
    module: tuple[ModulDTO, ...]
    hinweis: str
    ects_gesamt: int
    ects_soll_je_semester: int
    zielnote: Decimal | None                         # None ohne Notenziel
    zusatz: str = ""                                 # ausstehende Bewertungen (G)
    aktuelles_semester: int | None = None
