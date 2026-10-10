"""
Machbarkeitstest 2 - Grafische Oberflaeche und Diagramme mit Tkinter
=====================================================================
Leitfragen aus der Aufgabenstellung:
    "Welche Python-Bibliotheken sollen warum zum Einsatz kommen?"
    "Soll die Interaktion ueber die Kommandozeile oder ueber eine
     grafische Bedienoberflaeche erfolgen?"

Ziel des Tests
--------------
Der Pruefungsrechner ist ein Windows-PC ohne Administratorrechte und
ohne Internetzugang. Deshalb ist zu klaeren, ob sich die im Dashboard
benoetigten Anzeigeelemente ohne jede Fremdbibliothek - also
insbesondere ohne matplotlib - darstellen lassen.

Getestet werden die drei Darstellungsformen der Dashboard-Skizze:
    1. Ampel-Kachel      (Statusfarbe je Ziel)
    2. Fortschrittsbalken mit Soll-Marker (Ziel 1: Regelstudienzeit)
    3. Liniendiagramm mit Zielgerade      (Ziel 2: Notendurchschnitt)

Alle drei werden mit tkinter.Canvas gezeichnet. Tkinter ist Bestandteil
der Standardinstallation von CPython unter Windows und erfordert keine
Installation.

Aufruf:  python t2_tkinter_visualisierung.py
"""

from __future__ import annotations

import tkinter as tk

# Farbschema des Dashboards
FARBE_GRUEN, FARBE_GELB, FARBE_ROT = "#2e7d32", "#f9a825", "#c62828"
FARBE_HELL, FARBE_RAND, FARBE_TEXT = "#f4f6f8", "#b0bec5", "#212121"


def ampelfarbe(abweichung: float, toleranz: float) -> str:
    """
    Bildet eine Abweichung vom Ziel auf eine Ampelfarbe ab.

    abweichung < 0            -> Ziel uebertroffen oder eingehalten (gruen)
    0 <= abweichung <= toleranz -> Ziel knapp verfehlt (gelb)
    abweichung > toleranz     -> Ziel deutlich verfehlt (rot)
    """
    if abweichung < 0:
        return FARBE_GRUEN
    if abweichung <= toleranz:
        return FARBE_GELB
    return FARBE_ROT


def zeichne_kachel(canvas: tk.Canvas, x: int, y: int, breite: int, hoehe: int,
                   titel: str, wert: str, zusatz: str, farbe: str) -> None:
    """Eine Kennzahlen-Kachel mit farbigem Statusbalken am linken Rand."""
    canvas.create_rectangle(x, y, x + breite, y + hoehe,
                            fill="white", outline=FARBE_RAND)
    canvas.create_rectangle(x, y, x + 8, y + hoehe, fill=farbe, outline=farbe)
    canvas.create_text(x + 20, y + 16, anchor="w", text=titel,
                       font=("Helvetica", 9), fill="#546e7a")
    canvas.create_text(x + 20, y + 42, anchor="w", text=wert,
                       font=("Helvetica", 20, "bold"), fill=FARBE_TEXT)
    canvas.create_text(x + 20, y + 68, anchor="w", text=zusatz,
                       font=("Helvetica", 9), fill=farbe)


def zeichne_fortschrittsbalken(canvas: tk.Canvas, x: int, y: int, breite: int,
                               bestanden: int, laufend: int, soll: int,
                               maximum: int) -> None:
    """
    Gestapelter Fortschrittsbalken mit Soll-Marker.

    Der Balken trennt bereits bestandene von laufenden ECTS: Am
    Studienanfang sind fast alle ECTS "in Bearbeitung", und ein Balken,
    der nur Bestandenes zeigt, wuerde den Fortschritt zu pessimistisch
    darstellen.

    Der senkrechte Strich zeigt, wo man bei Studium in Regelstudienzeit
    stehen muesste. Erst dieser Vergleich macht den Balken zur
    Zielueberwachung statt zur reinen Statusanzeige.
    """
    hoehe = 26
    canvas.create_rectangle(x, y, x + breite, y + hoehe,
                            fill=FARBE_HELL, outline=FARBE_RAND)

    ende_bestanden = x + breite * bestanden / maximum
    ende_laufend = x + breite * (bestanden + laufend) / maximum
    if laufend > 0:
        canvas.create_rectangle(ende_bestanden, y, ende_laufend, y + hoehe,
                                fill="#90caf9", outline="#90caf9")
    if bestanden > 0:
        canvas.create_rectangle(x, y, ende_bestanden, y + hoehe,
                                fill=FARBE_GRUEN, outline=FARBE_GRUEN)

    marker = x + breite * soll / maximum
    canvas.create_line(marker, y - 9, marker, y + hoehe + 4,
                       fill=FARBE_TEXT, width=2)
    canvas.create_text(marker + 5, y - 12, anchor="w",
                       text=f"Soll heute: {soll} ECTS",
                       font=("Helvetica", 8), fill=FARBE_TEXT)
    canvas.create_text(x + breite + 10, y + hoehe // 2, anchor="w",
                       text=f"{bestanden + laufend} / {maximum}",
                       font=("Helvetica", 9))

    # Legende
    canvas.create_rectangle(x, y + hoehe + 12, x + 10, y + hoehe + 20,
                            fill=FARBE_GRUEN, outline=FARBE_GRUEN)
    canvas.create_text(x + 16, y + hoehe + 16, anchor="w",
                       text=f"bestanden ({bestanden})",
                       font=("Helvetica", 8), fill="#546e7a")
    canvas.create_rectangle(x + 130, y + hoehe + 12, x + 140, y + hoehe + 20,
                            fill="#90caf9", outline="#90caf9")
    canvas.create_text(x + 146, y + hoehe + 16, anchor="w",
                       text=f"in Bearbeitung ({laufend})",
                       font=("Helvetica", 8), fill="#546e7a")


def zeichne_notenverlauf(canvas: tk.Canvas, x: int, y: int, breite: int,
                         hoehe: int, werte: list[float], ziel: float) -> None:
    """
    Liniendiagramm des Notendurchschnitts mit waagerechter Zielgerade.

    Die Notenachse ist invertiert (1,0 oben), weil eine kleinere Note
    die bessere ist - eine nicht invertierte Achse wuerde eine
    Verbesserung als Abwaertstrend darstellen und damit fehlleiten.
    """
    oben, unten = 1.0, 4.0

    def y_pos(note: float) -> float:
        return y + (note - oben) / (unten - oben) * hoehe

    canvas.create_rectangle(x, y, x + breite, y + hoehe,
                            fill="white", outline=FARBE_RAND)
    for note in (1.0, 2.0, 3.0, 4.0):
        canvas.create_line(x, y_pos(note), x + breite, y_pos(note),
                           fill="#eceff1")
        canvas.create_text(x - 8, y_pos(note), anchor="e", text=f"{note:.1f}",
                           font=("Helvetica", 8), fill="#78909c")

    canvas.create_line(x, y_pos(ziel), x + breite, y_pos(ziel),
                       fill=FARBE_ROT, width=2, dash=(5, 3))
    canvas.create_text(x + breite + 8, y_pos(ziel), anchor="w",
                       text=f"Ziel {ziel:.1f}".replace(".", ","),
                       font=("Helvetica", 8), fill=FARBE_ROT)

    if len(werte) >= 2:
        schritt = breite / (len(werte) - 1)
        punkte = [(x + i * schritt, y_pos(w)) for i, w in enumerate(werte)]
        canvas.create_line(punkte, fill="#1565c0", width=2, smooth=False)
        for px, py in punkte:
            canvas.create_oval(px - 3, py - 3, px + 3, py + 3,
                               fill="#1565c0", outline="white")


def fenster_aufbauen() -> tk.Tk:
    """Baut das Testfenster mit allen drei Darstellungsformen auf."""
    fenster = tk.Tk()
    fenster.title("Machbarkeitstest 2 - Anzeigeelemente mit tkinter.Canvas")
    fenster.geometry("760x520")
    fenster.configure(bg=FARBE_HELL)

    canvas = tk.Canvas(fenster, width=760, height=520,
                       bg=FARBE_HELL, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    canvas.create_text(30, 28, anchor="w",
                       text="Anzeigeelemente des Studien-Dashboards",
                       font=("Helvetica", 14, "bold"), fill=FARBE_TEXT)
    canvas.create_text(30, 50, anchor="w",
                       text="gezeichnet allein mit tkinter.Canvas "
                            "(Standardbibliothek, keine Installation noetig)",
                       font=("Helvetica", 9), fill="#546e7a")

    # 1. Ampel-Kacheln
    # Ziel 1: 20 ECTS in Bearbeitung, Soll zur Semestermitte 15 -> auf Kurs
    zeichne_kachel(canvas, 30, 76, 340, 92, "ZIEL 1  Abschluss in 6 Semestern",
                   "Prognose: 6,0 Sem.", "auf Kurs (+5 ECTS Vorsprung)",
                   ampelfarbe(-5, 5))
    # Ziel 2: Schnitt 1,70 liegt unter dem Zielwert 1,9 -> gruen
    zeichne_kachel(canvas, 390, 76, 340, 92, "ZIEL 2  Notendurchschnitt <= 1,9",
                   "1,70", "Rest darf im Schnitt 1,91 sein",
                   ampelfarbe(1.70 - 1.9, 0.1))

    # 2. Gestapelter Fortschrittsbalken mit Soll-Marker
    canvas.create_text(30, 200, anchor="w", text="ECTS-Fortschritt im Studium",
                       font=("Helvetica", 10, "bold"), fill=FARBE_TEXT)
    zeichne_fortschrittsbalken(canvas, 30, 228, 560,
                               bestanden=5, laufend=20, soll=15, maximum=180)

    # 3. Liniendiagramm mit Zielgerade
    canvas.create_text(30, 300, anchor="w",
                       text="Entwicklung des Notendurchschnitts",
                       font=("Helvetica", 10, "bold"), fill=FARBE_TEXT)
    zeichne_notenverlauf(canvas, 60, 320, 530, 150,
                         werte=[2.3, 2.0, 1.9, 1.75, 1.7], ziel=1.9)

    canvas.create_text(30, 498, anchor="w",
                       text="Ergebnis: Kacheln, Balken und Liniendiagramm sind "
                            "ohne Fremdbibliothek darstellbar.",
                       font=("Helvetica", 9), fill=FARBE_GRUEN)
    return fenster


def main() -> None:
    fenster = fenster_aufbauen()
    print("Tkinter-Version:", tk.TkVersion)
    print("Fenster geoeffnet - zum Beenden schliessen.")
    fenster.mainloop()


if __name__ == "__main__":
    main()
