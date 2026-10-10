# Reflexion – Phase 2

Kleine, eigenständig lauffähige Testprogramme zur Frage, wie sich die
objektorientierten Konzepte aus dem Klassendiagramm der Phase 1 in Python
umsetzen lassen. Jedes Programm gibt seine Befunde nummeriert aus und
sichert sie mit `assert` ab; die letzte Zeile lautet bei Erfolg
„Alle Pruefungen bestanden.“

| Datei | Konzept | Untersucht an |
|---|---|---|
| `r1_kapselung.py` | Sichtbarkeit `-`/`+`, Kapselung | `Modul`: Unterstrich-Konvention, Name Mangling, `@property`, Dataclass mit privaten Feldern, `__dict__`, Closure als Alternative |
| `r2_abstraktion_vererbung.py` | Abstraktion, Vererbung, Polymorphie | `Pruefungsleistung` mit `Klausur`, `Portfolio`; `Studienziel` mit `ampelstatus()` (grün, gelb, rot) |
| `r3_komposition_aggregation.py` | Komposition, Aggregation | `Studiengang`–`Semester`, `Semester`–`Modul`, Lebensdauer mit `weakref` |
| `r4_typen_multiplizitaeten.py` | Aufzählungen, Datentypen, Multiplizitäten | `Pruefungsstatus`, `Decimal`, `[1..*]` bei `phasenfristen` |
| `r5_prozessgrenze.py` | Kapselung über eine Prozessgrenze (untersucht und für den Prototyp verworfen) | `DashboardServer` erzeugt den `DashboardController` über `erzeuge_controller()` in eigenem Prozess (`multiprocessing.managers`), Proxy mit freigegebenen Methoden, DTOs als Kopie |
| `r6_persistenz.py` | Speichern und Laden der Objektstruktur | Tabellen und Fremdschlüssel für Komposition und Aggregation, Unterklassen von `Pruefungsleistung` über die Spalte `art`, `phasenfristen` als eigene Tabelle, Bewertungsdatum und Notenverlauf |

## Ausführen

```
python r1_kapselung.py
python r2_abstraktion_vererbung.py
python r3_komposition_aggregation.py
python r4_typen_multiplizitaeten.py
python r5_prozessgrenze.py
python r6_persistenz.py
```

Ausschließlich Standardbibliothek. Getestet mit Python 3.10 und 3.14.7.
