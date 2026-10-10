"""Einziger Einstieg für Änderungen.

Der Service ruft die verändernden Operationen der Entity-Klassen auf; die
Regeln für ein einzelnes Objekt prüfen die Entity-Klassen. Hier liegt nur,
was mehrere Objekte betrifft: das Verschieben eines Moduls zwischen zwei
Semestern und die Plausibilitätsregeln, die den Studiengang (Studienbeginn,
Semesterzuordnung) oder den Stichtag brauchen.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from domain import Modul, Portfolio, Pruefungsstatus, Studiengang

#: Datumsformat für Fehlermeldungen im Dialog.
DATUM = "%d.%m.%Y"


class ErfassungsService:
    """Führt Eingaben aus dem Erfassungsdialog am Studiengang aus.

    Jede Methode prüft erst und ändert dann. Ein ValueError bedeutet, dass
    nichts geändert wurde; der Controller speichert in diesem Fall nicht.
    """

    def note_eintragen(self, sg: Studiengang, modul: Modul, note: Decimal, datum: date,
                       stichtag: date) -> None:
        """Trägt die Note ein, wenn sie zum Gesamtzustand passt.

        Abgelehnt werden (Phase 3, nach dem Zufallstest): ein Bewertungsdatum
        nach dem Stichtag oder vor dem Studienbeginn und eine Note für ein
        Modul, das keinem Semester zugeordnet ist. Bei einer Korrektur bleibt
        das alte Datum, deshalb gilt die Datumsprüfung nur für neue Noten.
        """
        if sg.semester_von(modul) is None:
            raise ValueError("Eine Note setzt voraus, dass das Modul einem Semester "
                             "zugeordnet ist")
        if modul.note() is None:
            if datum > stichtag:
                raise ValueError(f"Das Bewertungsdatum {datum:{DATUM}} liegt nach dem "
                                 f"Stichtag {stichtag:{DATUM}}")
            if datum < sg.startdatum:
                raise ValueError(f"Das Bewertungsdatum {datum:{DATUM}} liegt vor dem "
                                 f"Studienbeginn {sg.startdatum:{DATUM}}")
        modul.pruefungsleistung.note_eintragen(note, datum)

    def note_entfernen(self, modul: Modul) -> None:
        """Ergänzung in Phase 3: Note zurücknehmen, Status wird abgegeben."""
        modul.pruefungsleistung.note_entfernen()

    def status_setzen(self, modul: Modul, status: Pruefungsstatus) -> None:
        """Reicht den Status weiter; die Regeln prüft die Prüfungsleistung."""
        modul.pruefungsleistung.status_setzen(status)

    def phase_abgeben(self, portfolio: Portfolio) -> None:
        """Gibt die nächste Phase des Portfolios ab."""
        portfolio.phase_abgeben()

    def termin_setzen(self, sg: Studiengang, modul: Modul, datum: date) -> None:
        """Ergänzung in Phase 3: gebuchter Termin bzw. Frist aus dem Dialog."""
        if datum < sg.startdatum:
            raise ValueError(f"Der Termin {datum:{DATUM}} liegt vor dem Studienbeginn "
                             f"{sg.startdatum:{DATUM}}")
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
        if ziel is None and modul.note() is not None:
            raise ValueError("Ein benotetes Modul lässt sich nicht aus seinem Semester "
                             "entfernen, nur in ein anderes verschieben")
        if bisher is not None:
            bisher.modul_entfernen(modul)
        if ziel is not None:
            ziel.modul_zuordnen(modul)
