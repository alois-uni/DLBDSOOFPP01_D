# Studien-Dashboard

Prototyp eines Dashboards, das den eigenen Studienfortschritt überwacht: Abschluss in der Regelstudienzeit und Notendurchschnitt. Entstanden im Portfolio *Objektorientierte und funktionale Programmierung mit Python* (DLBDSOOFPP01_D) an der IU Internationalen Hochschule.

## Funktionen

- Ampeln für zwei Studienziele mit Prognose der Studiendauer und notwendigem Restdurchschnitt
- ECTS-Fortschritt mit tagesgenauem Sollwert, ECTS je Semester, Verlauf des Notendurchschnitts
- Modulübersicht des aktuellen Semesters und Hinweis auf die nächste anstehende Handlung
- Erfassen von Noten, Terminen, Status, Portfolio-Phasen und Semesterzuordnungen
- Speicherung in einer lokalen SQLite-Datenbank

## Voraussetzungen

- Python 3.10 oder neuer mit Tcl/Tk (unter Windows im Installer von python.org enthalten)
- keine weiteren Pakete, keine Administratorrechte, keine Internetverbindung

## Starten

Repository herunterladen (*Code → Download ZIP*) und entpacken oder klonen:

```
git clone https://github.com/alois-uni/DLBDSOOFPP01_D.git
cd DLBDSOOFPP01_D
```

Dann `start_dashboard.pyw` doppelklicken oder in der Eingabeaufforderung:

```
py start_dashboard.py
py start_dashboard.py --stichtag 2027-01-20
```

Unter macOS und Linux `python3` statt `py`.

## Tests

```
py -m unittest
```

Neben den Einzeltests spielt `tests/test_zufallsbedienung.py` Tausende zufällige Bedienfolgen sowie alle Folgen aus drei Aktionen je Prüfungsform durch und prüft nach jedem Schritt die fachlichen Regeln. Mit der Umgebungsvariablen `DASHBOARD_PROTOKOLL=protokoll.csv` schreibt er jeden Schritt in eine CSV-Datei.

## Projektstruktur

```
domain/          Entity-Klassen und fachliche Regeln
service/         Kennzahlen und Erfassung
repository/      Datenhaltung (SQLite, im Speicher für Tests)
dto/             Transportobjekte für die Oberfläche
controller/      Vermittlung zwischen Oberfläche und Fachlogik
ui/              Oberfläche mit tkinter
daten/           Stammdaten (CSV) und Beispieldatenbank
werkzeuge/       Erzeugen der Beispieldatenbank aus den CSV-Dateien
tests/           unittest-Tests
testprogramme/   Testprogramme aus Konzeption (Phase 1) und Reflexion (Phase 2)
```

## Daten

Beim ersten Start wird `daten/beispiel.db` nach `daten/studium.db` kopiert; alle Eingaben landen dort. Wer `studium.db` löscht, startet wieder mit den Beispieldaten. Die Beispieldaten entstehen aus `daten/module.csv` und `daten/stand.csv` mit `py werkzeuge/beispieldatenbank_erzeugen.py`.
