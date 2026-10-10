"""Einziger Einstieg für Änderungen.

Der Service ruft die verändernden Operationen der Entity-Klassen auf; die
Regeln selbst prüfen die Entity-Klassen. Hier liegt nur, was mehrere Objekte
betrifft, etwa das Verschieben eines Moduls zwischen zwei Semestern.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from domain import Modul, Portfolio, Pruefungsstatus, Studiengang


class ErfassungsService:
    def note_eintragen(self, modul: Modul, note: Decimal, datum: date) -> None:
        modul.pruefungsleistung.note_eintragen(note, datum)

    def note_entfernen(self, modul: Modul) -> None:
        """Ergänzung in Phase 3: Note zurücknehmen, Status wird abgegeben."""
        modul.pruefungsleistung.note_entfernen()

    def status_setzen(self, modul: Modul, status: Pruefungsstatus) -> None:
        modul.pruefungsleistung.status_setzen(status)

    def phase_abgeben(self, portfolio: Portfolio) -> None:
        portfolio.phase_abgeben()

    def termin_setzen(self, modul: Modul, datum: date) -> None:
        """Ergänzung in Phase 3: gebuchter Termin bzw. Frist aus dem Dialog."""
        modul.pruefungsleistung.termin_setzen(datum)

    def modul_zuordnen(self, sg: Studiengang, modul: Modul, nr: int) -> None:
        """Ordnet das Modul dem Semester nr zu; nr = 0 entfernt es aus seinem Semester.

        Erst wird geprüft, dann geändert, damit ein Fehler nichts halb verschiebt.
        """
        ziel = None
        if nr != 0:
            ziel = sg.semester(nr)
            if ziel is None:
                raise ValueError(f"Ein {nr}. Semester gibt es nicht")
        bisher = sg.semester_von(modul)
        if bisher is ziel:
            return
        if bisher is not None:
            bisher.modul_entfernen(modul)
        if ziel is not None:
            ziel.modul_zuordnen(modul)
