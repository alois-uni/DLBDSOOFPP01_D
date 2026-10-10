"""
Reflexionstest 1 - Sichtbarkeit und Kapselung
=============================================
Leitfrage: Wie bildet Python die UML-Sichtbarkeiten "-" (private) und
"+" (public) aus dem Klassendiagramm der Phase 1 ab?

Untersucht an der Entity-Klasse Modul:

  1. einfacher Unterstrich        _name   (Konvention)
  2. doppelter Unterstrich        __name  (Name Mangling)
  3. @property ohne Setter        nur lesender Zugriff
  4. @property mit Setter         Pruefung von Invarianten (zulaessige Notenstufen)
  5. @dataclass mit privaten Feldern
  6. Wo die Attribute liegen: der Namensraum des Objekts (__dict__)
  7. Closure: Zustand in einer lokalen Variable statt in einem Attribut
  8. Closure je Objekt im Konstruktor: Klasse und Vererbung bleiben erhalten
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Notenstufen der IU; eine Bereichspruefung allein liesse auch 2,2 oder 4,3 zu.
ZULAESSIGE_NOTEN = frozenset(Decimal(n) for n in (
    "1.0", "1.3", "1.7", "2.0", "2.3", "2.7", "3.0", "3.3", "3.7", "4.0", "5.0"))


class Modul:
    def __init__(self, kuerzel: str, ects: int) -> None:
        self._kuerzel = kuerzel          # "-" per Konvention
        self.__ects = ects               # "-" per Name Mangling
        self._note: Decimal | None = None

    @property
    def kuerzel(self) -> str:            # nur Getter: von aussen lesbar
        return self._kuerzel

    @property
    def note(self) -> Decimal | None:
        return self._note

    @note.setter
    def note(self, wert: Decimal) -> None:
        # Die Invariante steht an genau einer Stelle, jeder Schreibzugriff
        # laeuft zwangslaeufig hier durch.
        if wert not in ZULAESSIGE_NOTEN:
            raise ValueError(f"{wert} ist keine zulaessige Note")
        self._note = wert


def befund(nr: int, text: str) -> None:
    print(f"Befund {nr}: {text}")


m = Modul("DLBDSOOFPP01_D", 5)

# 1) Ein Unterstrich schuetzt nichts, er signalisiert nur.
m._kuerzel = "manipuliert"
assert m.kuerzel == "manipuliert"
m._kuerzel = "DLBDSOOFPP01_D"
befund(1, "_kuerzel ist von aussen les- und schreibbar, der Schutz ist reine Konvention.")

# 2) Zwei Unterstriche benennen das Attribut um, sperren es aber nicht.
try:
    _ = m.__ects                           # type: ignore[attr-defined]
    raise AssertionError("__ects haette nicht erreichbar sein sollen")
except AttributeError:
    pass
assert m._Modul__ects == 5                 # type: ignore[attr-defined]
befund(2, "m.__ects wirft AttributeError, m._Modul__ects liefert aber 5. "
          "Name Mangling verhindert Namenskollisionen in Unterklassen, keinen Zugriff.")

# 3) Property ohne Setter ergibt echten Lesezugriff auf Ebene der API.
try:
    m.kuerzel = "neu"                      # type: ignore[misc]
    raise AssertionError("Zuweisung haette scheitern sollen")
except AttributeError as e:
    befund(3, f"Zuweisung an kuerzel scheitert: {e}")

# 4) Setter prueft die Invariante.
m.note = Decimal("1.7")
abgelehnt = []
for unzulaessig in ("0.7", "2.2", "4.3"):
    try:
        m.note = Decimal(unzulaessig)
        raise AssertionError(f"Note {unzulaessig} haette abgelehnt werden sollen")
    except ValueError:
        abgelehnt.append(unzulaessig)
assert m.note == Decimal("1.7")
befund(4, f"Der Setter lehnt {abgelehnt} ab, auch die Werte innerhalb von 1,0 bis 5,0, "
          "die keine Notenstufe sind. Die alte Note 1.7 bleibt erhalten.")


# 5) Dataclass mit privaten Feldern: der Unterstrich wandert in den Konstruktor.
@dataclass
class ModulDC:
    _kuerzel: str
    _ects: int


dc = ModulDC(_kuerzel="DLBDSOOFPP01_D", _ects=5)
try:
    ModulDC(kuerzel="X", ects=5)           # type: ignore[call-arg]
    raise AssertionError("Aufruf ohne Unterstrich haette scheitern sollen")
except TypeError:
    pass
befund(5, "@dataclass uebernimmt den Feldnamen als Parameternamen. Bei privaten "
          "Feldern enthaelt deshalb jeder Aufruf mit Schluesselwort den Unterstrich, "
          "etwa ModulDC(_kuerzel=...); ModulDC(kuerzel=...) scheitert.")


# 6) Attribute liegen im Namensraum des Objekts, einem normalen Dictionary.
m2 = Modul("DLBDSOOFPP01_D", 5)
assert m2.__dict__["_Modul__ects"] == 5
befund(6, f"m.__dict__ enthaelt {sorted(m2.__dict__)}. Auch das umbenannte "
          "Attribut steht dort und ist damit von aussen erreichbar.")


# 7) Closure: die innere Funktion behaelt die lokale Variable der aeusseren.
def neues_modul(ects: int):
    def ects_lesen() -> int:
        return ects

    def ects_setzen(wert: int) -> None:
        nonlocal ects
        if not 1 <= wert <= 30:
            raise ValueError(f"{wert} ECTS sind ungueltig")
        ects = wert

    return ects_lesen, ects_setzen


ects_lesen, ects_setzen = neues_modul(5)
assert not hasattr(ects_lesen, "ects")
try:
    ects_setzen(0)
    raise AssertionError("0 ECTS haette abgelehnt werden sollen")
except ValueError:
    pass
zelle = ects_lesen.__closure__[0]
assert zelle.cell_contents == 5
zelle.cell_contents = 999                  # ohne Pruefung ueberschrieben
assert ects_lesen() == 999
befund(7, "In der Closure ist ects kein Attribut mehr, ects_setzen(0) wird "
          "abgelehnt. Ueber ects_lesen.__closure__[0].cell_contents laesst sich "
          "der Wert aber lesen und ohne Pruefung auf 999 setzen.")


# 8) Closure je Objekt: der Konstruktor legt eigene Zugriffsfunktionen an.
class Pruefungsleistung:
    def __init__(self, note=None):
        def note_lesen():
            return note

        def note_setzen(wert):
            nonlocal note
            if wert not in ZULAESSIGE_NOTEN:
                raise ValueError(f"{wert} ist keine zulaessige Note")
            note = wert

        self.note_lesen = note_lesen
        self.note_setzen = note_setzen


class Klausur(Pruefungsleistung):
    def __init__(self, termin, note=None):
        super().__init__(note)
        self.termin = termin


k1, k2 = Klausur("2026-12-04"), Klausur("2027-02-05")
k1.note_setzen(Decimal("1.7"))
assert k1.note_lesen() == Decimal("1.7") and k2.note_lesen() is None
try:
    k1.note_setzen(Decimal("0.7"))
    raise AssertionError("Note 0,7 haette abgelehnt werden sollen")
except ValueError:
    pass
assert sorted(k1.__dict__) == ["note_lesen", "note_setzen", "termin"]
k1.note_lesen.__closure__[0].cell_contents = Decimal("0.7")   # an der Pruefung vorbei
assert k1.note_lesen() == Decimal("0.7")
k2.note_setzen = lambda wert: None                             # Pruefung ersetzt
k2.note_setzen(Decimal("0.7"))
befund(8, "Legt der Konstruktor je Objekt eigene Zugriffsfunktionen an, bleiben "
          "Klasse, Vererbung und Pruefung erhalten; k1 und k2 haben getrennte Noten, "
          "und __dict__ enthaelt keine Note. Ueber __closure__ laesst sich die Note "
          "trotzdem auf 0.7 setzen, und die Pruefung faellt weg, wenn man "
          "note_setzen von aussen ersetzt.")

print("\nAlle Pruefungen bestanden.")
