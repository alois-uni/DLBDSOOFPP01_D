"""Vermittler zwischen Oberfläche und Fachlogik.

Der Controller lädt den Studiengang, lässt die Services rechnen und baut
daraus das DashboardDTO. Eingaben des Dialogs reicht er an den
ErfassungsService weiter und speichert anschließend. Lehnt eine
Entity-Klasse eine Eingabe mit ValueError ab, speichert er nichts und gibt
den Fehler an den Dialog weiter.

Er kennt nur die abstrakte Klasse StudiengangRepository; welche Umsetzung er
bekommt, entscheidet DashboardApp (Dependency Inversion).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from domain import (SETZBARE_STATUS, ZULAESSIGE_NOTEN, Abschlussziel, Modul, Notenziel,
                    Portfolio, Pruefungsstatus, Studiengang, Studienziel)
from dto import DashboardDTO, ModulDTO, ZielDTO
from repository import StudiengangRepository
from service.erfassungs_service import ErfassungsService
from service.kennzahlen_service import KennzahlenService, datum_text


def _zahl(wert: Decimal, stellen: int = 2) -> str:
    """Deutsche Schreibweise mit Komma, z. B. 1,90."""
    return f"{wert:.{stellen}f}".replace(".", ",")


class DashboardController:
    def __init__(self, repository: StudiengangRepository, kennzahlen: KennzahlenService,
                 erfassung: ErfassungsService, stichtag: date) -> None:
        self._repository = repository
        self._kennzahlen = kennzahlen
        self._erfassung = erfassung
        self._stichtag = stichtag
        self._studiengang: Studiengang = repository.lade()

    @property
    def stichtag(self) -> date:
        return self._stichtag

    # ------------------------------------------------------------ Anzeige
    def dashboard_daten(self) -> DashboardDTO:
        sg, tag = self._studiengang, self._stichtag
        aktuell = sg.aktuelles_semester(tag)
        module = aktuell.module if aktuell is not None else ()
        ausstehend = self._kennzahlen.ausstehende_bewertungen(sg)
        notenziel = next((z for z in sg.ziele if isinstance(z, Notenziel)), None)
        return DashboardDTO(
            kopfzeile=self._kopfzeile(sg, aktuell.nummer if aktuell else None),
            stichtag=tag,
            ziele=tuple(self._ziel_dto(nr, z) for nr, z in
                        enumerate((z for z in sg.ziele if z.ist_aktiv), start=1)),
            ects_bestanden=sg.bestandene_ects(),
            ects_laufend=self._kennzahlen.laufende_ects(sg),
            ects_soll_heute=sg.soll_ects(tag),
            ects_je_semester=tuple(self._kennzahlen.ects_je_semester(sg)),
            notenverlauf=tuple(self._kennzahlen.notenverlauf(sg)),
            module=tuple(self._modul_dto(m) for m in module),
            hinweis=self._kennzahlen.handlungshinweis(sg, tag),
            ects_gesamt=sg.gesamt_ects,
            ects_soll_je_semester=sg.gesamt_ects // max(sg.regelstudienzeit(), 1),
            zielnote=notenziel.ziel_durchschnitt if notenziel else None,
            zusatz=("Bewertung ausstehend: "
                    + ", ".join(f"«{m.bezeichnung}»" for m in ausstehend)) if ausstehend else "",
            aktuelles_semester=aktuell.nummer if aktuell else None,
        )

    def erfassbare_module(self) -> tuple[ModulDTO, ...]:
        """Alle Module für den Erfassungsdialog, auch bewertete (für Korrekturen).

        Ersetzt offene_module() aus Phase 2. Reihenfolge: nach Semester, dann
        der übrige Katalog, jeweils nach Kürzel.
        """
        module = sorted(self._studiengang.module,
                        key=lambda m: (self._semesternummer(m) or 99, m.kuerzel))
        return tuple(self._modul_dto(m) for m in module)

    def notenstufen(self) -> tuple[Decimal, ...]:
        """Zulässige Noten für die Auswahl im Dialog."""
        return tuple(sorted(ZULAESSIGE_NOTEN))

    def setzbare_status(self) -> tuple[Pruefungsstatus, ...]:
        return SETZBARE_STATUS

    def semesteranzahl(self) -> int:
        return self._studiengang.regelstudienzeit()

    # ------------------------------------------------------------ Erfassung
    def note_eintragen(self, kuerzel: str, note: Decimal, datum: date | None = None) -> None:
        """Trägt die Note ein; ohne Datum gilt der Stichtag als Bewertungsdatum."""
        modul = self._modul(kuerzel)
        bewertet_am = datum or self._stichtag
        self._aendern(lambda: self._erfassung.note_eintragen(modul, note, bewertet_am))

    def note_entfernen(self, kuerzel: str) -> None:
        """Ergänzung in Phase 3: Note zurücknehmen."""
        modul = self._modul(kuerzel)
        self._aendern(lambda: self._erfassung.note_entfernen(modul))

    def termin_setzen(self, kuerzel: str, datum: date) -> None:
        """Ergänzung in Phase 3: Prüfungstermin bzw. Frist eintragen."""
        modul = self._modul(kuerzel)
        self._aendern(lambda: self._erfassung.termin_setzen(modul, datum))

    def status_setzen(self, kuerzel: str, status: Pruefungsstatus) -> None:
        modul = self._modul(kuerzel)
        self._aendern(lambda: self._erfassung.status_setzen(modul, status))

    def phase_abgeben(self, kuerzel: str) -> None:
        pl = self._modul(kuerzel).pruefungsleistung
        if not isinstance(pl, Portfolio):          # einzige Typprüfung dieser Art
            raise ValueError("Phasen gibt es nur bei einem Portfolio")
        self._aendern(lambda: self._erfassung.phase_abgeben(pl))

    def modul_zuordnen(self, kuerzel: str, semester: int) -> None:
        """Ordnet das Modul einem Semester zu; semester = 0 entfernt die Zuordnung."""
        modul = self._modul(kuerzel)
        self._aendern(lambda: self._erfassung.modul_zuordnen(self._studiengang,
                                                             modul, semester))

    # ------------------------------------------------------------ intern
    def _aendern(self, aenderung) -> None:
        """Führt eine Änderung aus und speichert nur, wenn sie gelungen ist.

        Die Entity-Klassen prüfen vor dem Ändern; ein ValueError lässt den
        Studiengang deshalb unverändert. Scheitert das Speichern, wird der
        gespeicherte Stand neu geladen, damit Anzeige und Datei übereinstimmen.
        """
        aenderung()
        try:
            self._repository.speichere(self._studiengang)
        except Exception:
            self._studiengang = self._repository.lade()
            raise

    def _modul(self, kuerzel: str) -> Modul:
        modul = self._studiengang.modul(kuerzel)
        if modul is None:
            raise ValueError(f"Ein Modul {kuerzel} gibt es nicht")
        return modul

    def _semesternummer(self, modul: Modul) -> int | None:
        semester = self._studiengang.semester_von(modul)
        return semester.nummer if semester else None

    def _modul_dto(self, modul: Modul) -> ModulDTO:
        pl = modul.pruefungsleistung
        ist_portfolio = isinstance(pl, Portfolio)
        return ModulDTO(
            kuerzel=modul.kuerzel, bezeichnung=modul.bezeichnung, ects=modul.ects,
            pruefungsform=pl.FORM, status=pl.status, note=pl.note,
            naechster_termin=pl.naechster_termin(),
            semester=self._semesternummer(modul),
            ist_portfolio=ist_portfolio,
            phasen=pl.phasenstand() if ist_portfolio else "",
            bewertet_am=pl.bewertet_am, terminart=pl.terminart())

    @staticmethod
    def _kopfzeile(sg: Studiengang, semester: int | None) -> str:
        studiengang = f"{sg.bezeichnung} ({sg.abschluss.kurzform})"
        if semester is None:
            return f"{studiengang} · außerhalb der Regelstudienzeit"
        return f"{studiengang} · {semester}. Semester"

    def _ziel_dto(self, nr: int, ziel: Studienziel) -> ZielDTO:
        sg, tag = self._studiengang, self._stichtag
        ampel = ziel.ampelstatus(sg, tag)
        titel = f"ZIEL {nr} · {ziel.bezeichnung}"
        if isinstance(ziel, Abschlussziel):
            prognose = ziel.prognose_semester(sg, tag)
            wert = f"Prognose: {_zahl(prognose, 1)} Semester" if prognose else "Prognose: –"
            rueckstand = ziel.abweichung(sg, tag)
            lage = ("auf Kurs" if rueckstand <= 0 else
                    f"{_zahl(rueckstand, 0)} Modul(e) Rückstand")
            aussage = f"{lage} · {sg.bestandene_ects()} ECTS"
            aktuell = sg.aktuelles_semester(tag)
            if aktuell is not None:
                soll_ende = ziel.soll_in_modulstufen(
                    sg.soll_ects(aktuell.ende + timedelta(days=1)))
                aussage += f" · bis {datum_text(aktuell.ende)}: {soll_ende} ECTS"
            return ZielDTO(titel, wert, aussage, ampel)
        if isinstance(ziel, Notenziel):
            schnitt = sg.notendurchschnitt()
            wert = f"Ø {_zahl(schnitt)}" if schnitt is not None else "Ø –"
            rest = ziel.restdurchschnitt(sg)
            if schnitt is None:
                aussage = "noch keine Note eingetragen"
            elif rest is None:
                aussage = "alle ECTS bewertet"
            elif rest < Decimal("1.0"):
                aussage = "Ziel rechnerisch nicht mehr erreichbar"
            else:
                aussage = f"Rest darf im Schnitt {_zahl(rest)} sein"
            return ZielDTO(titel, wert, aussage, ampel)
        # Ein weiteres Ziel erscheint ohne Änderung der Anzeige mit seiner Abweichung.
        abweichung = ziel.abweichung(sg, tag)
        wert = _zahl(abweichung) if abweichung is not None else "–"
        return ZielDTO(titel, wert, "Abweichung vom Ziel", ampel)
