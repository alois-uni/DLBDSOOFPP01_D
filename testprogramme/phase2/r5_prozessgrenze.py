"""
Reflexionstest 5 - Prozessgrenze zwischen Oberflaeche und Fachlogik
===================================================================
Leitfrage: Laesst sich die Kapselung, die Python innerhalb eines Programms
nicht erzwingt, durch eine Grenze zwischen zwei Prozessen herstellen, und
passt das zur Architektur mit Controller und DTOs?

  1. Controller entsteht und laeuft in einem eigenen Prozess
     (Startart "spawn", wie sie unter Windows und macOS gilt)
  2. Die Oberflaeche erhaelt nur einen Stellvertreter (Proxy)
  3. Nur freigegebene Methoden sind aufrufbar
  4. DTOs kommen als unveraenderliche Kopie an
  5. Pruefregeln der Entity-Klassen greifen weiterhin
  6. Kosten eines Aufrufs ueber die Grenze

Alles aus der Standardbibliothek (multiprocessing.managers). Die Klassen
stehen auf Modulebene, weil der zweite Prozess dieses Modul neu importiert.

Ergebnis der Abwaegung im Reflexionsdokument (Abschnitt 2.3): Die Grenze
funktioniert, der Prototyp verzichtet aber darauf, weil der Aufwand fuer
ein Einzelplatzprogramm groesser ist als der Nutzen.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import time
from datetime import date
from dataclasses import FrozenInstanceError, dataclass
from decimal import Decimal
from multiprocessing.managers import BaseManager


ZULAESSIGE_NOTEN = frozenset(Decimal(n) for n in (
    "1.0", "1.3", "1.7", "2.0", "2.3", "2.7", "3.0", "3.3", "3.7", "4.0", "5.0"))


def befund(nr: int, text: str) -> None:
    print(f"Befund {nr}: {text}")


# ---------------------------------------------------------------- DTOs
@dataclass(frozen=True)
class ModulDTO:
    kuerzel: str
    ects: int
    note: Decimal | None


@dataclass(frozen=True)
class DashboardDTO:
    module: tuple[ModulDTO, ...]


# ---------------------------------------------------------------- Serverseite
class Modul:
    """Entity-Klasse; ihre Objekte verlassen den Serverprozess nie."""

    def __init__(self, kuerzel: str, ects: int) -> None:
        self._kuerzel = kuerzel
        self._ects = ects
        self._note: Decimal | None = None

    @property
    def note(self) -> Decimal | None:
        return self._note

    @note.setter
    def note(self, wert: Decimal) -> None:
        if wert not in ZULAESSIGE_NOTEN:
            raise ValueError(f"{wert} ist keine zulaessige Note")
        self._note = wert


class DashboardController:
    def __init__(self, stichtag: date) -> None:
        self._stichtag = stichtag
        self._module = {f"M{i:02d}": Modul(f"M{i:02d}", 5) for i in range(36)}

    def dashboard_daten(self) -> DashboardDTO:
        return DashboardDTO(tuple(ModulDTO(m._kuerzel, m._ects, m.note)
                                  for m in self._module.values()))

    def note_eintragen(self, kuerzel: str, note: Decimal) -> None:
        self._module[kuerzel].note = note

    def prozess(self) -> int:
        return os.getpid()

    def stichtag(self) -> date:
        return self._stichtag


class DashboardServer(BaseManager):
    """Startet den Serverprozess und legt die oeffentliche Schnittstelle fest."""

    @staticmethod
    def erzeuge_controller(stichtag: date) -> DashboardController:
        """Laeuft im Serverprozess; im Prototyp entstehen hier auch Repository
        und Services."""
        return DashboardController(stichtag)


DashboardServer.register(
    "DashboardController", DashboardServer.erzeuge_controller,
    exposed=["dashboard_daten", "note_eintragen", "prozess", "stichtag"])


# ---------------------------------------------------------------- Oberflaechenseite
def main() -> None:
    with DashboardServer(ctx=mp.get_context("spawn")) as server:
        heute = date.today()
        controller = server.DashboardController(heute)

        # 1) eigener Prozess
        assert controller.prozess() != os.getpid()
        assert controller.stichtag() == heute
        befund(1, f"Oberflaeche laeuft in Prozess {os.getpid()}, der Controller "
                  f"in Prozess {controller.prozess()}; erzeuge_controller() hat ihn "
                  f"dort mit dem Stichtag {heute.isoformat()} angelegt.")

        # 2) nur ein Stellvertreter
        assert not isinstance(controller, DashboardController)
        befund(2, f"Die Oberflaeche erhaelt ein Objekt vom Typ "
                  f"{type(controller).__name__}, keinen DashboardController.")

        # 3) nur freigegebene Methoden
        try:
            _ = controller._module
            raise AssertionError("_module haette nicht erreichbar sein sollen")
        except AttributeError:
            pass
        try:
            controller._callmethod("__getattribute__", ("_module",))
            raise AssertionError("Umweg haette abgelehnt werden sollen")
        except Exception as e:                       # RemoteError aus dem Server
            meldung = [z.strip() for z in str(e).splitlines() if "not in exposed" in z]
            assert meldung, str(e)
        befund(3, "_module ist am Stellvertreter nicht vorhanden; der Umweg ueber "
                  "__getattribute__ wird im Serverprozess abgelehnt: " + meldung[0])

        # 4) DTO als unveraenderliche Kopie
        daten = controller.dashboard_daten()
        assert isinstance(daten, DashboardDTO) and len(daten.module) == 36
        try:
            daten.module[0].note = Decimal("0.7")    # type: ignore[misc]
            raise AssertionError("DTO haette unveraenderlich sein sollen")
        except FrozenInstanceError:
            pass
        befund(4, f"dashboard_daten() liefert ein {type(daten).__name__} mit "
                  f"{len(daten.module)} Modulen; es ist eingefroren.")

        # 5) Pruefung im Serverprozess
        controller.note_eintragen("M00", Decimal("1.7"))
        try:
            controller.note_eintragen("M00", Decimal("0.7"))
            raise AssertionError("Note 0,7 haette abgelehnt werden sollen")
        except ValueError as e:
            fehler = str(e)
        assert controller.dashboard_daten().module[0].note == Decimal("1.7")
        befund(5, f"Die Note 0,7 wird im Serverprozess abgelehnt ({fehler}); "
                  "der ValueError kommt auf der Oberflaechenseite an.")

        # 6) Kosten
        n = 300
        t = time.perf_counter()
        for _ in range(n):
            controller.dashboard_daten()
        ueber_grenze = (time.perf_counter() - t) / n * 1000
        lokal = DashboardController(heute)
        t = time.perf_counter()
        for _ in range(n):
            lokal.dashboard_daten()
        im_prozess = (time.perf_counter() - t) / n * 1000
        befund(6, f"dashboard_daten() dauert ueber die Grenze {ueber_grenze:.2f} ms, "
                  f"im selben Prozess {im_prozess:.2f} ms.")

    print("\nAlle Pruefungen bestanden.")


if __name__ == "__main__":
    main()
