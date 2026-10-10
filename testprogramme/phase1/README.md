# Machbarkeitsüberprüfung – Phase 1

Kleine, eigenständig lauffähige Testprogramme zu den vier Leitfragen der
Aufgabenstellung. Alle Programme verwenden **ausschließlich die
Python-Standardbibliothek** und benötigen weder Administratorrechte noch
eine Internetverbindung.

| Datei | Leitfrage | Nachweis |
|---|---|---|
| `t1_sqlite_persistenz.py` | Dateien oder Datenbank? | Schema anlegen, schreiben, in einem zweiten Programmlauf wieder einlesen, Kennzahlen per SQL aggregieren |
| `t2_tkinter_visualisierung.py` | Kommandozeile oder GUI? Welche Bibliotheken? | Ampel-Kachel, Fortschrittsbalken mit Soll-Marker und Liniendiagramm, gezeichnet allein mit `tkinter.Canvas` |
| `t3_zielkennzahlen.py` | Sind die Ziele überhaupt messbar? | 10 `unittest`-Testfälle für gewichteten Notendurchschnitt, notwendigen Restdurchschnitt, Soll-ECTS und Abschlussprognose |

## Ausführen

```
python t1_sqlite_persistenz.py      # zweimal starten: zeigt die Persistenz
python t2_tkinter_visualisierung.py # öffnet ein Fenster
python t3_zielkennzahlen.py         # Beispielrechnung + Testlauf
```

Getestet mit Python 3.14.7; lauffähig ab Python 3.10.

`t1` legt beim ersten Lauf die Datei `machbarkeit_test.db` an. Zum
Wiederholen des Erstlaufs diese Datei löschen.
