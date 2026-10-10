"""Startmodul des Studien-Dashboards.

Aufruf:   py start_dashboard.py                      (Stichtag = heute)
          py start_dashboard.py --stichtag 2027-01-20

DashboardApp liegt außerhalb der Pakete, weil sie Objekte aller Schichten
erzeugt und damit keiner angehört. Sie ist die einzige Stelle, die die
konkrete Klasse SqliteStudiengangRepository kennt (Phase 2, Abschnitt 2.2).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

OHNE_TK = ("Dem installierten Python fehlt tkinter (Tcl/Tk), das zur Standardbibliothek "
           "gehört. Unter Windows Python von python.org installieren und die Option "
           "„tcl/tk and IDLE“ angehakt lassen; mit Homebrew passend zur Python-Version, "
           "z. B. brew install python-tk@3.14.")


def _abbrechen(text: str) -> None:
    """Meldet einen Startfehler auch dann, wenn kein Konsolenfenster offen ist (.pyw)."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "Studien-Dashboard", 0x10)
    sys.exit(text)


try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    _abbrechen(OHNE_TK)

PROGRAMMORDNER = Path(__file__).resolve().parent
sys.path.insert(0, str(PROGRAMMORDNER))      # Pakete auch beim Doppelklick finden

# Die eigenen Pakete werden erst nach der tkinter-Prüfung und dem Pfad
# importiert. "noqa: E402" sagt Prüfwerkzeugen wie flake8, dass die späten
# Importe gewollt sind.
from controller import DashboardController            # noqa: E402
from repository import SqliteStudiengangRepository    # noqa: E402
from service import ErfassungsService, KennzahlenService  # noqa: E402
from ui.dashboard_view import DashboardView           # noqa: E402

MINDESTVERSION = (3, 10)


class DashboardApp:
    """Erzeugt alle Objekte und verbindet sie (Composition Root).

    Repository, Services und Controller entstehen nur hier; die übrigen
    Klassen bekommen sie über ihren Konstruktor.
    """

    def __init__(self, stichtag: date, datenordner: Path) -> None:
        self._stichtag = stichtag
        self._datenordner = datenordner

    def _datenbank_bereitstellen(self) -> Path:
        """Kopiert beim ersten Start die Beispieldatenbank nach studium.db.

        Eingaben landen nur in studium.db; die Beispieldaten bleiben
        unverändert. Wer studium.db löscht, startet wieder mit ihnen.
        """
        arbeitskopie = self._datenordner / "studium.db"
        if not arbeitskopie.exists():
            shutil.copyfile(self._datenordner / "beispiel.db", arbeitskopie)
        return arbeitskopie

    def start(self) -> None:
        """Baut die Objekte auf und öffnet das Fenster; kehrt erst beim Schließen zurück."""
        repository = SqliteStudiengangRepository(self._datenbank_bereitstellen())
        controller = DashboardController(repository, KennzahlenService(),
                                         ErfassungsService(), self._stichtag)
        fenster = tk.Tk()
        DashboardView(fenster, controller)
        fenster.mainloop()


def _stichtag(text: str) -> date:
    """Wandelt --stichtag in ein Datum; argparse meldet Fehler mit Hinweis auf das Format."""
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} ist kein Datum im Format JJJJ-MM-TT")


def main(argumente: list[str] | None = None) -> None:
    """Einstieg für die Eingabeaufforderung und für start_dashboard.pyw."""
    if sys.version_info < MINDESTVERSION:
        _abbrechen("Das Studien-Dashboard braucht Python 3.10 oder neuer.")
    parser = argparse.ArgumentParser(description="Studien-Dashboard (Prototyp)")
    parser.add_argument("--stichtag", type=_stichtag, default=date.today(),
                        help="Datum, für das das Dashboard rechnet (JJJJ-MM-TT), "
                             "Standard: heute")
    args = parser.parse_args(argumente)
    try:
        DashboardApp(args.stichtag, PROGRAMMORDNER / "daten").start()
    except Exception as fehler:
        # Beim Doppelklick gibt es keine Konsole; der Fehler erscheint als Fenster.
        wurzel = tk.Tk()
        wurzel.withdraw()
        messagebox.showerror("Studien-Dashboard", f"Start fehlgeschlagen:\n{fehler}")
        wurzel.destroy()
        raise


if __name__ == "__main__":
    main()
