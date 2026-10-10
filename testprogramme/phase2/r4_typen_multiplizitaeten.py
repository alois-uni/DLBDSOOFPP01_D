"""
Reflexionstest 4 - Aufzaehlungen, Datentypen und Multiplizitaeten
=================================================================
Leitfrage: Wie werden die Aufzaehlungen, die Attributtypen und die
Multiplizitaeten aus dem Klassendiagramm der Phase 1 in Python abgebildet?

  1. UML-Enumeration -> enum.Enum
  2. Enum und gespeicherter Text
  3. Typannotationen werden zur Laufzeit nicht geprueft
  4. Multiplizitaet [1..*] braucht eine eigene Pruefung
  5. UML Real -> Decimal: aus Text erzeugen, nicht aus float
  6. veraenderlicher Standardwert in einer Dataclass
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


def befund(nr: int, text: str) -> None:
    print(f"Befund {nr}: {text}")


class Pruefungsstatus(Enum):
    GEPLANT = "geplant"
    ANGEMELDET = "angemeldet"
    ABGEGEBEN = "abgegeben"
    BESTANDEN = "bestanden"
    NICHT_BESTANDEN = "nichtBestanden"


# 1) Nur die definierten Werte sind moeglich.
assert Pruefungsstatus("bestanden") is Pruefungsstatus.BESTANDEN
try:
    Pruefungsstatus("bestnaden")
    raise AssertionError("Tippfehler haette abgelehnt werden sollen")
except ValueError as e:
    befund(1, f"Ungueltiger Wert wird abgelehnt: {e}")

# 2) Ein Enum-Wert ist kein String.
assert Pruefungsstatus.BESTANDEN != "bestanden"
assert Pruefungsstatus.BESTANDEN.value == "bestanden"
befund(2, "Pruefungsstatus.BESTANDEN == 'bestanden' ergibt False. In SQLite wird "
          ".value abgelegt und beim Laden mit Pruefungsstatus(text) zurueckgewandelt; "
          "genau diese Umwandlung gehoert ins Repository.")


# 3) Typannotationen sind Hinweise, keine Pruefung.
@dataclass
class ModulOhnePruefung:
    kuerzel: str
    ects: int


falsch = ModulOhnePruefung(kuerzel=42, ects="fuenf")      # type: ignore[arg-type]
assert falsch.ects == "fuenf"
befund(3, "ModulOhnePruefung(kuerzel=42, ects='fuenf') wird angenommen. Die "
          "Annotation int prueft erst ein externes Werkzeug wie mypy, nicht Python.")


# 4) [1..*] muss das Programm selbst sicherstellen.
@dataclass
class Portfolio:
    bezeichnung: str
    phasenfristen: list[date]

    def __post_init__(self) -> None:
        if not self.phasenfristen:
            raise ValueError("Portfolio braucht mindestens eine Phasenfrist [1..*]")


try:
    Portfolio("Portfolio OOP", [])
    raise AssertionError("leere Liste haette abgelehnt werden sollen")
except ValueError as e:
    befund(4, f"__post_init__ setzt die Untergrenze durch: {e}")

# 5) Decimal aus float uebernimmt den Binaerfehler.
aus_float = Decimal(1.9)
aus_text = Decimal("1.9")
assert aus_float != aus_text
befund(5, f"Decimal(1.9) = {aus_float}, Decimal('1.9') = {aus_text}. "
          "Noten werden deshalb aus Text erzeugt, passend zur TEXT-Spalte aus Phase 1.")

# 6) Veraenderlicher Standardwert: Dataclass verweigert die Definition.
try:
    @dataclass
    class Semester:                                           # noqa: F811
        nummer: int
        module: list = []                                     # type: ignore[assignment]
    raise AssertionError("Definition haette scheitern sollen")
except ValueError as e:
    befund(6, f"module: list = [] scheitert schon bei der Klassendefinition: {e}")


@dataclass
class Semester:
    nummer: int
    module: list[str] = field(default_factory=list)


a, b = Semester(1), Semester(2)
a.module.append("DLBDSOOFPP01_D")
assert b.module == []
print("         field(default_factory=list) gibt jedem Semester eine eigene Liste.")

print("\nAlle Pruefungen bestanden.")
