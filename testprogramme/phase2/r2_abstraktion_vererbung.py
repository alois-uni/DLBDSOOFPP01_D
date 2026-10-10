"""
Reflexionstest 2 - Abstraktion, Vererbung und Polymorphie
=========================================================
Leitfrage: Wie werden die abstrakten Klassen Pruefungsleistung und
Studienziel samt ihren Unterklassen aus Phase 1 in Python umgesetzt?

  1. abstrakte Klasse mit abc.ABC und @abstractmethod
  2. Zeitpunkt, zu dem eine fehlende Implementierung auffaellt
  3. super().__init__() fuer gemeinsame Attribute
  4. polymorpher Aufruf von naechster_termin() (Bereich G der Skizze)
  5. Polymorphie ohne Vererbung (Duck Typing)
  6. konkrete Methode der Oberklasse ruft abstrakte Methode auf
     (ampelstatus() -> abweichung(), Kacheln A und B)
  7. roter Bereich bei einem schlechteren Stand
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from enum import Enum


def befund(nr: int, text: str) -> None:
    print(f"Befund {nr}: {text}")


# ----------------------------------------------------------------------
# Pruefungsleistung
# ----------------------------------------------------------------------
class Pruefungsleistung(ABC):
    def __init__(self, bezeichnung: str) -> None:
        self._bezeichnung = bezeichnung
        self._note: Decimal | None = None

    def ist_bestanden(self) -> bool:     # fuer alle Formen gleich: konkret
        return self._note is not None and self._note <= Decimal("4.0")

    @abstractmethod
    def naechster_termin(self) -> date | None:
        """Jede Pruefungsform bestimmt ihren Termin selbst."""


class Klausur(Pruefungsleistung):
    def __init__(self, bezeichnung: str, pruefungstermin: date | None) -> None:
        super().__init__(bezeichnung)
        self._pruefungstermin = pruefungstermin

    def naechster_termin(self) -> date | None:
        return self._pruefungstermin


class Portfolio(Pruefungsleistung):
    def __init__(self, bezeichnung: str, phasenfristen: list[date]) -> None:
        super().__init__(bezeichnung)
        self._phasenfristen = sorted(phasenfristen)
        self._abgegebene_phasen = 0

    def phase_abgeben(self) -> None:
        self._abgegebene_phasen += 1

    def naechster_termin(self) -> date | None:
        # Kein gespeichertes Attribut: Frist der naechsten offenen Phase.
        offen = self._phasenfristen[self._abgegebene_phasen:]
        return offen[0] if offen else None


# 1) Abstrakte Klasse ist nicht instanziierbar.
try:
    Pruefungsleistung("x")                 # type: ignore[abstract]
    raise AssertionError("abstrakte Klasse haette nicht instanziierbar sein sollen")
except TypeError as e:
    befund(1, f"Pruefungsleistung() scheitert: {e}")


# 2) Vergessene Implementierung: die Klassendefinition gelingt!
class AdvancedWorkbook(Pruefungsleistung):
    def __init__(self, bezeichnung: str, abgabefrist: date) -> None:
        super().__init__(bezeichnung)
        self._abgabefrist = abgabefrist
    # naechster_termin() fehlt absichtlich


try:
    AdvancedWorkbook("Workbook", date(2026, 11, 30))
    raise AssertionError("fehlende Implementierung haette auffallen sollen")
except TypeError:
    befund(2, "AdvancedWorkbook ohne naechster_termin() laesst sich fehlerfrei "
              "definieren. Der Fehler faellt erst beim Erzeugen eines Objekts auf, "
              "also erst zur Laufzeit.")

# 3) super().__init__() setzt die gemeinsamen Attribute.
k = Klausur("Klausur Mathe", date(2026, 12, 4))
assert k._bezeichnung == "Klausur Mathe" and k._note is None
befund(3, "super().__init__() belegt bezeichnung und note in der Oberklasse, "
          "die Unterklasse ergaenzt nur ihr eigenes Attribut.")

# 4) Polymorphie: ein Aufruf, verschiedene Umsetzungen.
p = Portfolio("Portfolio OOP", [date(2026, 9, 15), date(2026, 10, 27), date(2026, 12, 8)])
p.phase_abgeben()
leistungen: list[Pruefungsleistung] = [k, p]
termine = [t for t in (l.naechster_termin() for l in leistungen) if t is not None]
assert min(termine) == date(2026, 10, 27)
befund(4, f"naechster Termin ueber alle Leistungen: {min(termine)} "
          "(Portfolio, Phase 2), ohne isinstance-Abfrage im Aufrufer.")


# 5) Duck Typing: ein Objekt ohne gemeinsame Oberklasse passt ebenso.
class Erinnerung:
    def naechster_termin(self) -> date | None:
        return date(2026, 10, 1)


gemischt = [k, p, Erinnerung()]
assert min(x.naechster_termin() for x in gemischt) == date(2026, 10, 1)
assert not isinstance(Erinnerung(), Pruefungsleistung)
befund(5, "Die Schleife akzeptiert auch Erinnerung, die nicht von Pruefungsleistung "
          "erbt. Python verlangt fuer Polymorphie keine Vererbung, die ABC dient "
          "als dokumentierter und beim Erzeugen gepruefter Vertrag.")


# ----------------------------------------------------------------------
# Studienziel: konkrete Methode ruft abstrakte Methode
# ----------------------------------------------------------------------
class Ampel(Enum):
    GRUEN = "gruen"
    GELB = "gelb"
    ROT = "rot"


class Studienziel(ABC):
    def __init__(self, bezeichnung: str, toleranz: Decimal) -> None:
        self._bezeichnung = bezeichnung
        self._toleranz = toleranz

    @abstractmethod
    def abweichung(self, stand: dict) -> Decimal:
        """Abweichung vom Ziel in der Einheit der Toleranz, <= 0 heisst erreicht.

        In Phase 1 hiess die Operation zielerreichungsgrad(). Die Ampel
        braucht aber einen Rueckstand, der sich direkt mit der Toleranz
        vergleichen laesst; ein Grad in Prozent muesste erst umgerechnet werden.
        """

    def ampelstatus(self, stand: dict) -> Ampel:   # nur hier umgesetzt
        abweichung = self.abweichung(stand)
        if abweichung <= 0:
            return Ampel.GRUEN
        if abweichung <= self._toleranz:
            return Ampel.GELB
        return Ampel.ROT


class Abschlussziel(Studienziel):
    def abweichung(self, stand: dict) -> Decimal:
        rueckstand_ects = stand["soll_ects"] - stand["bestandene_ects"]
        return Decimal(rueckstand_ects) / 5          # in Modulen


class Notenziel(Studienziel):
    def __init__(self, bezeichnung: str, toleranz: Decimal, ziel: Decimal) -> None:
        super().__init__(bezeichnung, toleranz)
        self._ziel = ziel

    def abweichung(self, stand: dict) -> Decimal:
        return stand["durchschnitt"] - self._ziel     # in Notenpunkten


# Stand zum Stichtag der Skizze aus Phase 1
stand = {"soll_ects": 25, "bestandene_ects": 25, "durchschnitt": Decimal("2.00")}
ziele: list[Studienziel] = [
    Abschlussziel("Regelstudienzeit", toleranz=Decimal("1")),
    Notenziel("Schnitt 1,9", toleranz=Decimal("0.1"), ziel=Decimal("1.9")),
]
ampeln = [z.ampelstatus(stand) for z in ziele]
assert ampeln == [Ampel.GRUEN, Ampel.GELB]
befund(6, f"ampelstatus() existiert einmal und liefert {[a.value for a in ampeln]}, "
          "wie in der Skizze. Die Methode braucht aber einen Parameter mit dem "
          "Stand zum Stichtag; im Diagramm der Phase 1 ist sie parameterlos.")

# 7) Roter Bereich: schlechterer Stand als in der Skizze
stand_rot = {"soll_ects": 25, "bestandene_ects": 15, "durchschnitt": Decimal("2.10")}
ampeln_rot = [z.ampelstatus(stand_rot) for z in ziele]
assert ampeln_rot == [Ampel.ROT, Ampel.ROT]
befund(7, "Bei 15 von 25 ECTS (2 Module Rueckstand, Toleranz 1) und Schnitt 2,10 "
          "(0,2 ueber dem Ziel, Toleranz 0,1) liefert ampelstatus() "
          f"{[a.value for a in ampeln_rot]}.")

print("\nAlle Pruefungen bestanden.")
