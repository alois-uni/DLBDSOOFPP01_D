"""Dialog zum Erfassen von Noten, Terminen, Statusänderungen, Abgaben und Semesterzuordnungen.

Der Dialog kennt den Controller, die DTOs und die Aufzählung Pruefungsstatus,
aber keine Entity-Klasse. Ob eine Eingabe zulässig ist, prüfen die
Entity-Klassen; eine Ablehnung (ValueError) zeigt der Dialog als Meldung an,
gespeichert wird dann nichts.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from tkinter import ttk

from controller import DashboardController
from domain import Pruefungsstatus
from dto import ModulDTO

GRUEN, ROT, GRAU = "#2e7d32", "#c62828", "#546e7a"
DATUMSFORMAT = "%d.%m.%Y"


def _note_text(note: Decimal) -> str:
    """Note mit einer Nachkommastelle und Dezimalkomma, z. B. 1,3."""
    return f"{note:.1f}".replace(".", ",")


class ErfassungsDialog:
    """Eigenes Fenster für alle Eingaben zu einem ausgewählten Modul.

    Nach jeder gespeicherten Änderung ruft der Dialog bei_aenderung auf,
    damit das Dashboard neu zeichnet, und lädt seine Modulliste neu.
    Knöpfe, die für das gewählte Modul nichts bewirken können, sind
    ausgegraut.
    """

    def __init__(self, eltern: tk.Misc, controller: DashboardController,
                 bei_aenderung: Callable[[], None]) -> None:
        self._controller = controller
        self._bei_aenderung = bei_aenderung
        self._module: tuple[ModulDTO, ...] = ()

        self._fenster = tk.Toplevel(eltern)
        self._fenster.title("Daten erfassen")
        self._fenster.resizable(False, False)
        self._fenster.transient(eltern)
        rahmen = ttk.Frame(self._fenster, padding=14)
        rahmen.grid(sticky="nsew")

        ttk.Label(rahmen, text="Modul").grid(row=0, column=0, sticky="w")
        self._auswahl = ttk.Combobox(rahmen, state="readonly", width=78)
        self._auswahl.grid(row=0, column=1, columnspan=3, sticky="we", pady=(0, 4))
        self._auswahl.bind("<<ComboboxSelected>>", lambda _e: self._zeige_modul())
        self._info = ttk.Label(rahmen, foreground=GRAU)
        self._info.grid(row=1, column=1, columnspan=3, sticky="w", pady=(0, 10))

        # Ein Datumsfeld für Bewertungsdatum und Termin, vorbelegt mit dem Stichtag
        ttk.Label(rahmen, text="Datum").grid(row=2, column=0, sticky="w")
        self._datum = ttk.Entry(rahmen, width=12)
        self._datum.insert(0, f"{controller.stichtag:{DATUMSFORMAT}}")
        self._datum.grid(row=2, column=1, sticky="w", pady=3)
        ttk.Label(rahmen, text="TT.MM.JJJJ, gilt für Note und Termin",
                  foreground=GRAU).grid(row=2, column=2, sticky="w")

        self._noten = controller.notenstufen()
        ttk.Label(rahmen, text="Note").grid(row=3, column=0, sticky="w")
        self._note = ttk.Combobox(rahmen, state="readonly", width=8,
                                  values=[_note_text(n) for n in self._noten])
        self._note.grid(row=3, column=1, sticky="w", pady=3)
        self._note_knopf = ttk.Button(rahmen, text="Note eintragen",
                                      command=self._note_eintragen)
        self._note_knopf.grid(row=3, column=2, sticky="we")
        self._entfernen_knopf = ttk.Button(rahmen, text="Note entfernen",
                                           command=self._note_entfernen)
        self._entfernen_knopf.grid(row=3, column=3, sticky="we", padx=(6, 0))

        ttk.Label(rahmen, text="Termin").grid(row=4, column=0, sticky="w")
        self._termin_knopf = ttk.Button(rahmen, text="Termin setzen",
                                        command=self._termin_setzen)
        self._termin_knopf.grid(row=4, column=2, sticky="we", pady=3)

        self._status_werte = controller.setzbare_status()
        ttk.Label(rahmen, text="Status").grid(row=5, column=0, sticky="w")
        self._status = ttk.Combobox(rahmen, state="readonly", width=14,
                                    values=[s.anzeige for s in self._status_werte])
        self._status.grid(row=5, column=1, sticky="w", pady=3)
        self._status_knopf = ttk.Button(rahmen, text="Status setzen",
                                        command=self._status_setzen)
        self._status_knopf.grid(row=5, column=2, sticky="we")

        ttk.Label(rahmen, text="Portfolio").grid(row=6, column=0, sticky="w")
        self._phase = ttk.Button(rahmen, text="Nächste Phase abgeben",
                                 command=self._phase_abgeben)
        self._phase.grid(row=6, column=2, sticky="we", pady=3)

        self._semester_werte = ["kein Semester"] + [
            f"{nr}. Semester" for nr in range(1, controller.semesteranzahl() + 1)]
        ttk.Label(rahmen, text="Semester").grid(row=7, column=0, sticky="w")
        self._semester = ttk.Combobox(rahmen, state="readonly", width=14,
                                      values=self._semester_werte)
        self._semester.grid(row=7, column=1, sticky="w", pady=3)
        self._zuordnen_knopf = ttk.Button(rahmen, text="Zuordnen",
                                          command=self._modul_zuordnen)
        self._zuordnen_knopf.grid(row=7, column=2, sticky="we")

        self._meldung = ttk.Label(rahmen, wraplength=560)
        self._meldung.grid(row=8, column=0, columnspan=4, sticky="w", pady=(12, 6))
        ttk.Button(rahmen, text="Schließen",
                   command=self._fenster.destroy).grid(row=9, column=3, sticky="e")

        self._lade_module()

    # ------------------------------------------------------------ für die View
    def ist_offen(self) -> bool:
        """Ist das Fenster noch geöffnet? Verhindert einen zweiten Dialog."""
        return bool(self._fenster.winfo_exists())

    def nach_vorne(self) -> None:
        """Holt den offenen Dialog vor das Hauptfenster."""
        self._fenster.lift()
        self._fenster.focus_force()

    # ------------------------------------------------------------ Anzeige
    def _lade_module(self, kuerzel: str | None = None) -> None:
        """Füllt die Modulauswahl neu und wählt kuerzel wieder aus."""
        self._module = self._controller.erfassbare_module()
        texte = []
        for m in self._module:
            ort = f"S{m.semester}" if m.semester else "Wahl"
            texte.append(f"{ort} · {m.bezeichnung} ({m.pruefungsform}, {m.status.anzeige})")
        self._auswahl["values"] = texte
        index = next((i for i, m in enumerate(self._module) if m.kuerzel == kuerzel), None)
        if index is None:          # ohne Vorgabe: erstes noch nicht bestandenes Modul
            index = next((i for i, m in enumerate(self._module)
                          if m.status is not Pruefungsstatus.BESTANDEN), 0)
        if self._module:
            self._auswahl.current(index)
        self._zeige_modul()

    def _gewaehlt(self) -> ModulDTO | None:
        index = self._auswahl.current()
        return self._module[index] if 0 <= index < len(self._module) else None

    def _zeige_modul(self) -> None:
        """Zeigt den Stand des gewählten Moduls und passt Knöpfe und Beschriftungen an."""
        modul = self._gewaehlt()
        if modul is None:
            return
        teile = [f"Kürzel {modul.kuerzel}", f"{modul.ects} ECTS", modul.status.anzeige,
                 f"Versuch {modul.versuch} von {modul.max_versuche}"]
        if modul.note is not None:
            teile.append(f"Note {_note_text(modul.note)}"
                         + (f" vom {modul.bewertet_am:{DATUMSFORMAT}}" if modul.bewertet_am else ""))
        if modul.phasen:
            teile.append(modul.phasen)
        if modul.naechster_termin:
            teile.append(f"nächster Termin {modul.naechster_termin:{DATUMSFORMAT}}")
        self._info["text"] = " · ".join(teile)
        self._note_knopf["text"] = ("Note korrigieren (Datum bleibt)" if modul.note is not None
                                    else "Note eintragen (Bewertungsdatum = Datum)")
        self._termin_knopf["text"] = f"{modul.terminart} setzen (= Datum)"
        # Termine gibt es nur für geplante oder angemeldete Prüfungen
        offen = modul.status in (Pruefungsstatus.GEPLANT, Pruefungsstatus.ANGEMELDET)
        self._termin_knopf.state(["!disabled"] if offen else ["disabled"])
        self._phase.state(["!disabled"] if modul.ist_portfolio else ["disabled"])
        self._entfernen_knopf.state(["!disabled"] if modul.note is not None else ["disabled"])
        self._semester.current(modul.semester or 0)
        self._status.set(modul.status.anzeige if modul.status in self._status_werte else "")

    # ------------------------------------------------------------ Aktionen
    def _speichern(self, aktion: Callable[[ModulDTO], None], erfolg: str) -> None:
        """Führt eine Erfassung über den Controller aus und meldet das Ergebnis."""
        modul = self._gewaehlt()
        if modul is None:
            return
        try:
            aktion(modul)
        except ValueError as fehler:
            self._melde(f"Nicht gespeichert: {fehler}.")
            return
        except Exception as fehler:     # z. B. Datenbankdatei gesperrt
            self._melde(f"Speichern fehlgeschlagen: {fehler}")
            return
        self._meldung.configure(text=f"{erfolg}: {modul.bezeichnung}", foreground=GRUEN)
        self._bei_aenderung()
        self._lade_module(modul.kuerzel)

    def _melde(self, text: str) -> None:
        """Zeigt eine Fehlermeldung in Rot unter den Eingaben."""
        self._meldung.configure(text=text, foreground=ROT)

    def _gelesenes_datum(self) -> date | None:
        """Wandelt die Eingabe an der Grenze in ein Datum; meldet Tippfehler."""
        text = self._datum.get().strip()
        try:
            return datetime.strptime(text, DATUMSFORMAT).date()
        except ValueError:
            self._melde(f"„{text}“ ist kein Datum im Format TT.MM.JJJJ.")
            return None

    def _note_eintragen(self) -> None:
        index = self._note.current()
        if index < 0:
            self._melde("Bitte zuerst eine Note wählen.")
            return
        datum = self._gelesenes_datum()
        if datum is None:
            return
        note = self._noten[index]
        self._speichern(lambda m: self._controller.note_eintragen(m.kuerzel, note, datum),
                        f"Note {_note_text(note)} gespeichert")

    def _note_entfernen(self) -> None:
        self._speichern(lambda m: self._controller.note_entfernen(m.kuerzel),
                        "Note entfernt, Status jetzt „abgegeben“")

    def _termin_setzen(self) -> None:
        datum = self._gelesenes_datum()
        if datum is None:
            return
        self._speichern(lambda m: self._controller.termin_setzen(m.kuerzel, datum),
                        f"Termin {datum:{DATUMSFORMAT}} gesetzt")

    def _status_setzen(self) -> None:
        index = self._status.current()
        if index < 0:
            self._melde("Bitte zuerst einen Status wählen.")
            return
        status: Pruefungsstatus = self._status_werte[index]
        self._speichern(lambda m: self._controller.status_setzen(m.kuerzel, status),
                        f"Status „{status.anzeige}“ gesetzt")

    def _phase_abgeben(self) -> None:
        self._speichern(lambda m: self._controller.phase_abgeben(m.kuerzel),
                        "Phase abgegeben")

    def _modul_zuordnen(self) -> None:
        nr = max(self._semester.current(), 0)
        text = self._semester_werte[nr]
        self._speichern(lambda m: self._controller.modul_zuordnen(m.kuerzel, nr),
                        f"Zugeordnet zu „{text}“")
