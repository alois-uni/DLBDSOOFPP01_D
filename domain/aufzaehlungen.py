"""Aufzählungen des Entity-Modells (Abb. A.2 in Phase 2).

Die Werte entsprechen den Literalen im Klassendiagramm. Sie werden als Text
gespeichert, im Programm aber immer als Enum verwendet, damit ein Tippfehler
wie "bestnden" sofort auffällt und nicht als gültiger Zustand weiterläuft.
"""

from __future__ import annotations

from enum import Enum


class Abschlussgrad(Enum):
    BACHELOR_OF_SCIENCE = "bachelorOfScience"
    BACHELOR_OF_ARTS = "bachelorOfArts"
    MASTER_OF_SCIENCE = "masterOfScience"
    MASTER_OF_ARTS = "masterOfArts"

    @property
    def kurzform(self) -> str:
        """Kurzform für die Kopfzeile, z. B. "B.Sc."."""
        return {
            Abschlussgrad.BACHELOR_OF_SCIENCE: "B.Sc.",
            Abschlussgrad.BACHELOR_OF_ARTS: "B.A.",
            Abschlussgrad.MASTER_OF_SCIENCE: "M.Sc.",
            Abschlussgrad.MASTER_OF_ARTS: "M.A.",
        }[self]


class Pruefungsstatus(Enum):
    GEPLANT = "geplant"
    ANGEMELDET = "angemeldet"
    ABGEGEBEN = "abgegeben"
    BESTANDEN = "bestanden"
    NICHT_BESTANDEN = "nichtBestanden"

    @property
    def anzeige(self) -> str:
        """Bezeichnung für die Oberfläche."""
        return "nicht bestanden" if self is Pruefungsstatus.NICHT_BESTANDEN else self.value


class Ampel(Enum):
    GRUEN = "gruen"
    GELB = "gelb"
    ROT = "rot"
