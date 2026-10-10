"""Darstellung des Dashboards mit tkinter.Canvas (Skizze aus Phase 1, Bereiche A bis G).

Die View erhält ausschließlich DTOs und zeigt keine Entity-Objekte an. Aus
dem Paket domain kennt sie nur die Aufzählungen Ampel und Pruefungsstatus,
aus denen sie die Farben ableitet.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from decimal import Decimal
from tkinter import ttk

from controller import DashboardController
from domain import Ampel, Pruefungsstatus
from dto import DashboardDTO, ModulDTO
from ui.erfassungs_dialog import ErfassungsDialog

# Farbschema der Skizze
GRUEN, GELB, ROT = "#2e7d32", "#f9a825", "#c62828"
BLAU, BLAU_HELL = "#1565c0", "#90caf9"
HINTERGRUND, RAND, GRAU, TEXT, KOPF = "#f4f6f8", "#b0bec5", "#78909c", "#212121", "#263238"
LINIEN = "#eceff1"
GEPLANT = "#cfd8dc"

AMPELFARBE = {Ampel.GRUEN: GRUEN, Ampel.GELB: GELB, Ampel.ROT: ROT}
STATUSFARBE = {
    Pruefungsstatus.GEPLANT: GRAU,
    Pruefungsstatus.ANGEMELDET: BLAU,
    Pruefungsstatus.ABGEGEBEN: "#ef6c00",
    Pruefungsstatus.BESTANDEN: GRUEN,
    Pruefungsstatus.NICHT_BESTANDEN: ROT,
}

RAND_AUSSEN, ABSTAND = 16, 10
MIN_BREITE, HOEHE = 1040, 690


def _zahl(wert: Decimal, stellen: int = 1) -> str:
    return f"{wert:.{stellen}f}".replace(".", ",")


class DashboardView:
    def __init__(self, fenster: tk.Tk, controller: DashboardController) -> None:
        self._fenster = fenster
        self._controller = controller
        self._daten: DashboardDTO | None = None
        self._dialog: ErfassungsDialog | None = None
        self._nachzeichnen: str | None = None

        fenster.title("Studien-Dashboard")
        hoehe = max(HOEHE, min(760, fenster.winfo_screenheight() - 80))
        fenster.geometry(f"{MIN_BREITE + 60}x{hoehe}")
        fenster.minsize(MIN_BREITE, HOEHE)
        fenster.configure(bg=HINTERGRUND)

        familie = "Segoe UI" if "Segoe UI" in tkfont.families(fenster) else "Helvetica"
        self._schrift = {
            "klein": (familie, 8), "normal": (familie, 9), "fett": (familie, 9, "bold"),
            "titel": (familie, 10, "bold"), "kopf": (familie, 13, "bold"),
            "gross": (familie, 20, "bold"),
        }
        self._messen = tkfont.Font(fenster, font=self._schrift["normal"])
        self._messen_fett = tkfont.Font(fenster, font=self._schrift["fett"])

        self._canvas = tk.Canvas(fenster, bg=HINTERGRUND, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._knopf = ttk.Button(fenster, text="Daten erfassen …",
                                 command=self._oeffne_erfassung)
        self._canvas.bind("<Configure>", self._groesse_geaendert)
        self.aktualisiere()

    # ------------------------------------------------------------ öffentlich
    def aktualisiere(self) -> None:
        """Fordert ein neues DTO an und zeichnet alles neu."""
        self._daten = self._controller.dashboard_daten()
        self._zeichne(self._daten)

    # ------------------------------------------------------------ Ereignisse
    def _groesse_geaendert(self, _ereignis) -> None:
        if self._nachzeichnen:
            self._fenster.after_cancel(self._nachzeichnen)
        self._nachzeichnen = self._fenster.after(
            60, lambda: self._daten and self._zeichne(self._daten))

    def _oeffne_erfassung(self) -> None:
        if self._dialog is not None and self._dialog.ist_offen():
            self._dialog.nach_vorne()
            return
        self._dialog = ErfassungsDialog(self._fenster, self._controller,
                                        bei_aenderung=self.aktualisiere)

    # ------------------------------------------------------------ Zeichnen
    def _zeichne(self, daten: DashboardDTO) -> None:
        c = self._canvas
        c.delete("all")
        breite = max(c.winfo_width(), MIN_BREITE)
        x0, x1 = RAND_AUSSEN, breite - RAND_AUSSEN
        mitte = (x0 + x1) // 2
        y = RAND_AUSSEN

        y = self._zeichne_kopf(daten, x0, x1, y) + ABSTAND
        hoehe_ab = 90
        for i, ziel in enumerate(daten.ziele[:2]):
            links = x0 if i == 0 else mitte + ABSTAND // 2
            rechts = mitte - ABSTAND // 2 if i == 0 else x1
            self._zeichne_kachel(links, y, rechts, y + hoehe_ab, ziel.titel, ziel.wert,
                                 ziel.aussage, AMPELFARBE[ziel.ampel], "AB"[i])
        y += hoehe_ab + ABSTAND

        self._zeichne_fortschritt(daten, x0, y, x1, y + 80)
        y += 80 + ABSTAND

        hoehe_de = 165
        self._zeichne_notenverlauf(daten, x0, y, mitte - ABSTAND // 2, y + hoehe_de)
        self._zeichne_semester(daten, mitte + ABSTAND // 2, y, x1, y + hoehe_de)
        y += hoehe_de + ABSTAND

        hoehe_g = 48
        unten = max(c.winfo_height(), HOEHE) - RAND_AUSSEN
        self._zeichne_module(daten, x0, y, x1, unten - hoehe_g - ABSTAND)
        self._zeichne_hinweis(daten, x0, unten - hoehe_g, x1, unten)

    def _rahmen(self, x0, y0, x1, y1, kennung: str, titel: str | None = None) -> None:
        c = self._canvas
        c.create_rectangle(x0, y0, x1, y1, fill="white", outline=RAND)
        c.create_text(x1 - 6, y0 + 4, anchor="ne", text=kennung,
                      font=self._schrift["klein"], fill=GRAU)
        if titel:
            c.create_text(x0 + 12, y0 + 14, anchor="w", text=titel,
                          font=self._schrift["titel"], fill=TEXT)

    def _zeichne_kopf(self, daten: DashboardDTO, x0, x1, y) -> int:
        c, hoehe = self._canvas, 44
        c.create_rectangle(x0, y, x1, y + hoehe, fill=KOPF, outline=KOPF)
        c.create_text(x0 + 14, y + hoehe / 2, anchor="w", text="Studien-Dashboard",
                      font=self._schrift["kopf"], fill="white")
        c.create_text(x0 + 220, y + hoehe / 2, anchor="w", text=daten.kopfzeile,
                      font=self._schrift["normal"], fill="#cfd8dc")
        c.create_text(x1 - 170, y + hoehe / 2, anchor="e",
                      text=f"Stand: {daten.stichtag:%d.%m.%Y}",
                      font=self._schrift["normal"], fill="#cfd8dc")
        c.create_window(x1 - 12, y + hoehe / 2, anchor="e", window=self._knopf)
        return y + hoehe

    def _zeichne_kachel(self, x0, y0, x1, y1, titel, wert, aussage, farbe, kennung) -> None:
        c = self._canvas
        self._rahmen(x0, y0, x1, y1, kennung)
        c.create_rectangle(x0, y0, x0 + 8, y1, fill=farbe, outline=farbe)
        c.create_text(x0 + 22, y0 + 16, anchor="w", text=titel,
                      font=self._schrift["normal"], fill=GRAU)
        c.create_text(x0 + 22, y0 + 43, anchor="w", text=wert,
                      font=self._schrift["gross"], fill=TEXT)
        c.create_text(x0 + 22, y0 + 71, anchor="w", text=aussage,
                      font=self._schrift["normal"], fill=farbe)

    def _zeichne_fortschritt(self, daten: DashboardDTO, x0, y0, x1, y1) -> None:
        c = self._canvas
        self._rahmen(x0, y0, x1, y1, "C", "ECTS-Fortschritt im Gesamtstudium")
        bx0, bx1, by = x0 + 14, x1 - 150, y0 + 36
        hoehe, gesamt = 22, daten.ects_gesamt
        skala = (bx1 - bx0) / gesamt
        c.create_rectangle(bx0, by, bx1, by + hoehe, fill=HINTERGRUND, outline=RAND)
        ende_b = bx0 + daten.ects_bestanden * skala
        ende_l = ende_b + daten.ects_laufend * skala
        if daten.ects_laufend:
            c.create_rectangle(ende_b, by, ende_l, by + hoehe, fill=BLAU_HELL, outline=BLAU_HELL)
        if daten.ects_bestanden:
            c.create_rectangle(bx0, by, ende_b, by + hoehe, fill=GRUEN, outline=GRUEN)
        marker = bx0 + float(daten.ects_soll_heute) * skala
        c.create_line(marker, by - 6, marker, by + hoehe + 6, fill=TEXT, width=2)
        c.create_text(marker + 4, by + hoehe + 12, anchor="w",
                      text=f"Soll heute: {_zahl(daten.ects_soll_heute)} ECTS",
                      font=self._schrift["klein"], fill=TEXT)
        c.create_text(x1 - 136, by + hoehe / 2, anchor="w",
                      text=f"{daten.ects_bestanden + daten.ects_laufend} / {gesamt} ECTS",
                      font=self._schrift["fett"], fill=TEXT)
        lx = (bx0 + bx1) / 2
        for farbe, text in ((GRUEN, f"bestanden ({daten.ects_bestanden})"),
                            (BLAU_HELL, f"in Bearbeitung ({daten.ects_laufend})")):
            c.create_rectangle(lx, by + hoehe + 8, lx + 10, by + hoehe + 16,
                               fill=farbe, outline=farbe)
            c.create_text(lx + 14, by + hoehe + 12, anchor="w", text=text,
                          font=self._schrift["klein"], fill=GRAU)
            lx += 130

    def _zeichne_notenverlauf(self, daten: DashboardDTO, x0, y0, x1, y1) -> None:
        c = self._canvas
        self._rahmen(x0, y0, x1, y1, "D", "Entwicklung des Notendurchschnitts")
        gx0, gx1, gy0, gy1 = x0 + 46, x1 - 70, y0 + 34, y1 - 30
        oben, unten = Decimal("1.0"), Decimal("4.0")

        def y_pos(note: Decimal) -> float:     # invertierte Achse: 1,0 oben
            return gy0 + float((note - oben) / (unten - oben)) * (gy1 - gy0)

        for stufe in ("1.0", "2.0", "3.0", "4.0"):
            yy = y_pos(Decimal(stufe))
            c.create_line(gx0, yy, gx1, yy, fill=LINIEN)
            c.create_text(gx0 - 8, yy, anchor="e", text=stufe.replace(".", ","),
                          font=self._schrift["klein"], fill=GRAU)
        if daten.zielnote is not None:
            yz = y_pos(daten.zielnote)
            c.create_line(gx0, yz, gx1, yz, fill=ROT, width=2, dash=(5, 3))
            c.create_text(gx1 + 6, yz, anchor="w",
                          text=f"Ziel {_zahl(daten.zielnote)}",
                          font=self._schrift["klein"], fill=ROT)
        werte = daten.notenverlauf
        if not werte:
            c.create_text((gx0 + gx1) / 2, (gy0 + gy1) / 2, text="noch keine Note",
                          font=self._schrift["normal"], fill=GRAU)
        else:
            schritt = (gx1 - gx0) / max(len(werte) - 1, 1)
            punkte = [(gx0 + i * schritt if len(werte) > 1 else (gx0 + gx1) / 2, y_pos(w))
                      for i, w in enumerate(werte)]
            if len(punkte) > 1:
                c.create_line(punkte, fill=BLAU, width=2)
            for px, py in punkte:
                c.create_oval(px - 3, py - 3, px + 3, py + 3, fill=BLAU, outline="white")
            c.create_text(punkte[-1][0], punkte[-1][1] - 10, anchor="s",
                          text=_zahl(werte[-1], 2), font=self._schrift["klein"], fill=BLAU)
        c.create_text(gx0, y1 - 12, anchor="w",
                      text="Zeitachse: Reihenfolge der Bewertungen",
                      font=self._schrift["klein"], fill=GRAU)

    def _zeichne_semester(self, daten: DashboardDTO, x0, y0, x1, y1) -> None:
        c = self._canvas
        self._rahmen(x0, y0, x1, y1, "E", "ECTS je Semester, Ist gegen Soll")
        gx0, gx1, gy0, gy1 = x0 + 40, x1 - 20, y0 + 34, y1 - 42
        soll = daten.ects_soll_je_semester or 30
        maximum = max([soll] + [sum(werte) for werte in daten.ects_je_semester])
        skala = (gy1 - gy0) / maximum
        for wert in (0, soll):
            yy = gy1 - wert * skala
            c.create_line(gx0, yy, gx1, yy, fill=LINIEN)
            c.create_text(gx0 - 8, yy, anchor="e", text=str(wert),
                          font=self._schrift["klein"], fill=GRAU)
        anzahl = max(len(daten.ects_je_semester), 1)
        spalte = (gx1 - gx0) / anzahl
        for i, (bestanden, laufend, geplant) in enumerate(daten.ects_je_semester):
            sx0 = gx0 + i * spalte + spalte * 0.2
            sx1 = gx0 + (i + 1) * spalte - spalte * 0.2
            c.create_rectangle(sx0, gy1 - soll * skala, sx1, gy1, outline=GRAU, dash=(3, 3))
            if bestanden:
                c.create_rectangle(sx0, gy1 - bestanden * skala, sx1, gy1,
                                   fill=GRUEN, outline=GRUEN)
            if laufend:
                oben = gy1 - (bestanden + laufend) * skala
                c.create_rectangle(sx0, oben, sx1, gy1 - bestanden * skala,
                                   fill=BLAU_HELL, outline=BLAU_HELL)
            if geplant:
                unten = gy1 - (bestanden + laufend) * skala
                c.create_rectangle(sx0, unten - geplant * skala, sx1, unten,
                                   fill=GEPLANT, outline=GEPLANT)
            aktuell = (i + 1) == daten.aktuelles_semester
            c.create_text((sx0 + sx1) / 2, gy1 + 10, text=f"{i + 1}.",
                          font=self._schrift["fett" if aktuell else "klein"],
                          fill=TEXT if aktuell else GRAU)
        c.create_text(gx0, y1 - 12, anchor="w",
                      text=f"gestrichelt: Soll {soll} ECTS je Semester · grau: geplant",
                      font=self._schrift["klein"], fill=GRAU)

    def _zeichne_module(self, daten: DashboardDTO, x0, y0, x1, y1) -> None:
        c = self._canvas
        titel = ("Module im aktuellen Semester" if daten.aktuelles_semester
                 else "Module (kein laufendes Semester)")
        self._rahmen(x0, y0, x1, y1, "F", titel)
        breite = x1 - x0 - 24
        spalten = [("Modul", 0.0), ("ECTS", 0.42), ("Prüfungsform", 0.47),
                   ("Status", 0.62), ("Note", 0.80), ("nächster Termin", 0.86)]
        kx = [x0 + 12 + anteil * breite for _, anteil in spalten]
        yk = y0 + 36
        for (name, _), x in zip(spalten, kx):
            c.create_text(x, yk, anchor="w", text=name, font=self._schrift["fett"], fill=GRAU)
        c.create_line(x0 + 10, yk + 10, x1 - 10, yk + 10, fill=RAND)
        if not daten.module:
            c.create_text(x0 + 12, yk + 28, anchor="w",
                          text="Diesem Semester ist noch kein Modul zugeordnet.",
                          font=self._schrift["normal"], fill=GRAU)
            return
        zeile = 19
        platz = int((y1 - (yk + 22)) // zeile)
        for i, modul in enumerate(daten.module[:platz]):
            yy = yk + 26 + i * zeile
            self._zeile(modul, kx, yy, kx[1] - kx[0] - 12)
        if len(daten.module) > platz:
            c.create_text(x1 - 12, y1 - 10, anchor="e",
                          text=f"… {len(daten.module) - platz} weitere",
                          font=self._schrift["klein"], fill=GRAU)

    def _zeile(self, modul: ModulDTO, kx: list[float], y: float, namensbreite: float) -> None:
        c, n = self._canvas, self._schrift["normal"]
        status = modul.status.anzeige
        if modul.ist_portfolio and modul.status is Pruefungsstatus.ANGEMELDET:
            status += f", {modul.phasen}".replace(" Phasen abgegeben", " Ph.")
        werte = [self._kuerzen(modul.bezeichnung, namensbreite), str(modul.ects),
                 modul.pruefungsform, status,
                 _zahl(modul.note) if modul.note is not None else "–",
                 f"{modul.naechster_termin:%d.%m.%Y}" if modul.naechster_termin else "–"]
        for i, (wert, x) in enumerate(zip(werte, kx)):
            farbe = STATUSFARBE[modul.status] if i == 3 else TEXT
            c.create_text(x, y, anchor="w", text=wert, font=n, fill=farbe)

    def _zeichne_hinweis(self, daten: DashboardDTO, x0, y0, x1, y1) -> None:
        c = self._canvas
        self._rahmen(x0, y0, x1, y1, "G")
        c.create_rectangle(x0, y0, x0 + 8, y1, fill=GELB, outline=GELB)
        text = self._kuerzen(f"Nächste Handlung: {daten.hinweis}", x1 - x0 - 50, fett=True)
        c.create_text(x0 + 22, y0 + (15 if daten.zusatz else (y1 - y0) / 2), anchor="w",
                      text=text, font=self._schrift["fett"], fill=TEXT)
        if daten.zusatz:
            c.create_text(x0 + 22, y0 + 33, anchor="w",
                          text=self._kuerzen(daten.zusatz, x1 - x0 - 50),
                          font=self._schrift["normal"], fill=GRAU)

    def _kuerzen(self, text: str, breite: float, fett: bool = False) -> str:
        """Kürzt Text mit Auslassungszeichen auf die verfügbare Breite."""
        messen = self._messen_fett if fett else self._messen
        if messen.measure(text) <= breite:
            return text
        while text and messen.measure(text + "…") > breite:
            text = text[:-1]
        return text.rstrip() + "…"
