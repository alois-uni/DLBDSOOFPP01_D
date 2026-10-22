"""Prüfungsleistung und ihre Prüfungsformen.

Die Prüfungsformen unterscheiden sich darin, woraus sich ihr nächster Termin
ergibt (Phase 1, Kap. 3). naechster_termin() ist deshalb abstrakt und wird in
jeder Unterklasse umgesetzt; aufrufender Code fragt nie nach der Form.

Alle Regeln, die genau eine Prüfungsleistung betreffen, liegen hier:
zulässige Notenstufen, höchstens drei Versuche, erlaubte Statuswechsel.
Jede verändernde Methode prüft zuerst und ändert erst danach den Zustand,
damit ein abgelehnter Aufruf das Objekt unverändert lässt.

Erweiterungen gegenüber dem Entwurf aus Phase 2 (in den Klassendiagrammen
blau markiert):
  * vierte Unterklasse SchriftlicheArbeit für Seminar, Bachelorarbeit und
    Praktikum
  * Phasenfristen eines Portfolios mit Multiplizität [0..3], weil die
    Fristen erst nach der Einschreibung feststehen; ein Portfolio hat immer
    drei Phasen, die Abgabe der dritten ist die finale Abgabe
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from domain.aufzaehlungen import Pruefungsstatus

# Notenstufen nach Prüfungsordnung; 5,0 heißt nicht bestanden.
ZULAESSIGE_NOTEN = frozenset(Decimal(n) for n in (
    "1.0", "1.3", "1.7", "2.0", "2.3", "2.7", "3.0", "3.3", "3.7", "4.0", "5.0"))
BESTEHENSGRENZE = Decimal("4.0")
MAX_VERSUCHE = 3
PHASEN_JE_PORTFOLIO = 3

# Status, die man von Hand setzen darf. Bestanden und nicht bestanden
# ergeben sich ausschließlich aus einer eingetragenen Note.
SETZBARE_STATUS = (Pruefungsstatus.GEPLANT, Pruefungsstatus.ANGEMELDET,
                   Pruefungsstatus.ABGEGEBEN)


class Pruefungsleistung(ABC):
    """Abstrakte Oberklasse aller Prüfungsformen.

    Der Konstruktor nimmt auch gespeicherten Zustand an (status, note,
    bewertet_am ...) und prüft ihn wie jede andere Eingabe. So fällt eine
    von Hand in der Datenbank geänderte Note beim Laden auf (r6, Befund 6).
    """

    #: Anzeigename der Prüfungsform, von jeder Unterklasse überschrieben.
    FORM = "Prüfungsleistung"

    def __init__(self, *, bezeichnung: str | None = None,
                 status: Pruefungsstatus = Pruefungsstatus.GEPLANT,
                 versuchsnummer: int = 1,
                 note: Decimal | None = None,
                 bewertet_am: date | None = None,
                 zieltermin: date | None = None) -> None:
        if not 1 <= versuchsnummer <= MAX_VERSUCHE:
            raise ValueError(f"Versuch {versuchsnummer} ist nicht zulässig "
                             f"(höchstens {MAX_VERSUCHE})")
        if note is not None and note not in ZULAESSIGE_NOTEN:
            raise ValueError(f"{note} ist keine zulässige Note")
        if (note is None) != (bewertet_am is None):
            raise ValueError("Note und Bewertungsdatum gehören zusammen")
        if note is not None and status is not self._status_fuer(note):
            raise ValueError(f"Status {status.value} passt nicht zur Note {note}")
        if note is None and status in (Pruefungsstatus.BESTANDEN,
                                       Pruefungsstatus.NICHT_BESTANDEN):
            raise ValueError(f"Status {status.value} ohne Note ist nicht möglich")
        self._bezeichnung = bezeichnung or self.FORM
        self._status = status
        self._versuchsnummer = versuchsnummer
        self._note = note
        self._bewertet_am = bewertet_am
        self._zieltermin = zieltermin

    # ------------------------------------------------------------ lesen
    @property
    def bezeichnung(self) -> str:
        return self._bezeichnung

    @property
    def status(self) -> Pruefungsstatus:
        return self._status

    @property
    def versuchsnummer(self) -> int:
        return self._versuchsnummer

    @property
    def note(self) -> Decimal | None:
        return self._note

    @property
    def bewertet_am(self) -> date | None:
        """Tag, an dem die Note eingetragen wurde; ordnet den Notenverlauf."""
        return self._bewertet_am

    @property
    def zieltermin(self) -> date | None:
        """Selbst geplanter Termin, solange kein Termin gebucht ist (Skizze, G)."""
        return self._zieltermin

    def ist_bestanden(self) -> bool:
        """Für alle Formen gleich und deshalb nicht abstrakt."""
        return self._status is Pruefungsstatus.BESTANDEN

    def ist_offen(self) -> bool:
        """Noch etwas zu tun: geplant oder angemeldet, aber nicht abgegeben."""
        return self._status in (Pruefungsstatus.GEPLANT, Pruefungsstatus.ANGEMELDET)

    @abstractmethod
    def naechster_termin(self) -> date | None:
        """Nächster relevanter Termin; None, wenn keiner ansteht."""

    def naechste_aufgabe(self) -> str:
        """Was zum nächsten Termin zu tun ist (Text für Bereich G)."""
        return "abgeben"

    def ist_selbst_geplant(self) -> bool:
        """Ist der nächste Termin nur der Zieltermin, weil noch nichts gebucht ist?

        Bereich G weist dann darauf hin, dass der Termin noch zu buchen ist.
        Ein Vergleich der Daten genügt nicht: Ein gebuchter Termin kann auf
        denselben Tag fallen wie der Zieltermin.
        """
        return (self.ist_offen() and self._zieltermin is not None
                and self._gebuchter_termin() is None)

    # ------------------------------------------------------------ ändern
    def status_setzen(self, status: Pruefungsstatus) -> None:
        """Setzt geplant, angemeldet oder abgegeben.

        Eine Anmeldung nach einem nicht bestandenen Versuch beginnt den
        nächsten Versuch; mehr als drei Versuche lässt die Methode nicht zu.
        Der neue Versuch beginnt ohne Note und ohne die Termine und Fristen
        des alten, die sonst sofort als überschritten gemeldet würden.
        """
        if status not in SETZBARE_STATUS:
            raise ValueError("Bestanden und nicht bestanden ergeben sich aus der Note")
        if self._status is Pruefungsstatus.BESTANDEN:
            raise ValueError("Die Prüfung ist bereits bestanden")
        if self._status is Pruefungsstatus.NICHT_BESTANDEN:
            if status is not Pruefungsstatus.ANGEMELDET:
                raise ValueError("Nach einem nicht bestandenen Versuch ist nur "
                                 "eine neue Anmeldung möglich")
            if self._versuchsnummer >= MAX_VERSUCHE:
                raise ValueError(f"Alle {MAX_VERSUCHE} Versuche sind verbraucht")
            self._versuchsnummer += 1
            self._note = None
            self._bewertet_am = None
            self._termine_leeren()
        self._status = status

    def note_eintragen(self, note: Decimal, datum: date) -> None:
        """Trägt die Note ein und setzt den Status auf bestanden oder nicht bestanden.

        Eine Note geht aus jedem Status. Ist schon eine Note eingetragen, gilt
        die neue als Korrektur: Das Bewertungsdatum bleibt dann, damit ein
        berichtigter Tippfehler die Reihenfolge im Notenverlauf nicht verschiebt.
        """
        if note not in ZULAESSIGE_NOTEN:
            raise ValueError(f"{note} ist keine zulässige Note")
        if self._note is None:
            self._bewertet_am = datum
        self._note = note
        self._status = self._status_fuer(note)

    def termin_setzen(self, datum: date) -> None:
        """Trägt den gebuchten Termin bzw. die Frist ein, solange die Prüfung offen ist."""
        if not self.ist_offen():
            raise ValueError("Ein Termin lässt sich nur für eine geplante oder "
                             f"angemeldete Prüfung setzen (Status: {self._status.anzeige})")
        self._termin_eintragen(datum)

    @abstractmethod
    def _termin_eintragen(self, datum: date) -> None:
        """Jede Prüfungsform weiß, welches Attribut ihr Termin ist."""

    @abstractmethod
    def _gebuchter_termin(self) -> date | None:
        """Gegenstück zu _termin_eintragen: der gebuchte Termin bzw. die Frist, sonst None."""

    @abstractmethod
    def _termine_leeren(self) -> None:
        """Entfernt die gebuchten Termine bzw. Fristen für einen neuen Versuch.

        Der selbst geplante Zieltermin bleibt, er gehört zu keinem Versuch.
        """

    @abstractmethod
    def terminart(self) -> str:
        """Bezeichnung des Termins, den termin_setzen() setzt (für den Dialog)."""

    def note_entfernen(self) -> None:
        """Nimmt eine eingetragene Note zurück, etwa nach einem Versehen.

        Der Status wird abgegeben: Die Prüfung gilt als erbracht, die
        Bewertung als ausstehend. Der Versuch bleibt derselbe.
        """
        if self._note is None:
            raise ValueError("Es ist keine Note eingetragen")
        self._note = None
        self._bewertet_am = None
        self._status = Pruefungsstatus.ABGEGEBEN

    @staticmethod
    def _status_fuer(note: Decimal) -> Pruefungsstatus:
        return (Pruefungsstatus.BESTANDEN if note <= BESTEHENSGRENZE
                else Pruefungsstatus.NICHT_BESTANDEN)

    def _termin_oder_ziel(self, termin: date | None) -> date | None:
        """Hilfe für die Unterklassen: gebuchter Termin, sonst Zieltermin."""
        if not self.ist_offen():
            return None
        return termin if termin is not None else self._zieltermin


class Klausur(Pruefungsleistung):
    """Klausur; der nächste Termin ist der gebuchte Prüfungstermin.

    Ohne Buchung zeigt das Dashboard den selbst geplanten Zieltermin.
    """

    FORM = "Klausur"

    def __init__(self, pruefungstermin: date | None = None, **zustand) -> None:
        super().__init__(**zustand)
        self._pruefungstermin = pruefungstermin

    @property
    def pruefungstermin(self) -> date | None:
        return self._pruefungstermin

    def naechster_termin(self) -> date | None:
        return self._termin_oder_ziel(self._pruefungstermin)

    def naechste_aufgabe(self) -> str:
        return "Klausur schreiben"

    def _termin_eintragen(self, datum: date) -> None:
        self._pruefungstermin = datum

    def _gebuchter_termin(self) -> date | None:
        return self._pruefungstermin

    def _termine_leeren(self) -> None:
        self._pruefungstermin = None

    def terminart(self) -> str:
        return "Prüfungstermin"


class AdvancedWorkbook(Pruefungsleistung):
    """Advanced Workbook mit einer einzigen Abgabefrist."""

    FORM = "Advanced Workbook"

    def __init__(self, abgabefrist: date | None = None, **zustand) -> None:
        super().__init__(**zustand)
        self._abgabefrist = abgabefrist

    @property
    def abgabefrist(self) -> date | None:
        return self._abgabefrist

    def naechster_termin(self) -> date | None:
        return self._termin_oder_ziel(self._abgabefrist)

    def _termin_eintragen(self, datum: date) -> None:
        self._abgabefrist = datum

    def _gebuchter_termin(self) -> date | None:
        return self._abgabefrist

    def _termine_leeren(self) -> None:
        self._abgabefrist = None

    def terminart(self) -> str:
        return "Abgabefrist"


class SchriftlicheArbeit(Pruefungsleistung):
    """Seminararbeit, Bachelorarbeit, Praktikumsbericht: eine Abgabefrist.

    Ergänzt in Phase 3. Nötig waren nur diese Klasse, ein Wert in der
    CHECK-Bedingung und ein Zweig im Repository; kein aufrufender Code
    musste sich ändern (Open-Closed-Prinzip, Phase 1, Kap. 3).
    """

    FORM = "Schriftliche Arbeit"

    def __init__(self, abgabefrist: date | None = None, **zustand) -> None:
        super().__init__(**zustand)
        self._abgabefrist = abgabefrist

    @property
    def abgabefrist(self) -> date | None:
        return self._abgabefrist

    def naechster_termin(self) -> date | None:
        return self._termin_oder_ziel(self._abgabefrist)

    def _termin_eintragen(self, datum: date) -> None:
        self._abgabefrist = datum

    def _gebuchter_termin(self) -> date | None:
        return self._abgabefrist

    def _termine_leeren(self) -> None:
        self._abgabefrist = None

    def terminart(self) -> str:
        return "Abgabefrist"


class Portfolio(Pruefungsleistung):
    """Portfolio mit drei Phasen; die Abgabe der dritten ist die finale Abgabe.

    Der nächste Termin ist nicht gespeichert, sondern ergibt sich als Frist
    der ersten noch nicht abgegebenen Phase. Die Fristen dürfen fehlen
    ([0..3]), solange man nicht eingeschrieben ist, und werden im Dialog
    nacheinander für Phase 1, 2 und 3 eingetragen.
    """

    FORM = "Portfolio"

    def __init__(self, phasenfristen: list[date] | tuple[date, ...] = (),
                 abgegebene_phasen: int = 0, **zustand) -> None:
        super().__init__(**zustand)
        fristen = sorted(phasenfristen)
        if len(fristen) > PHASEN_JE_PORTFOLIO:
            raise ValueError(f"Ein Portfolio hat {PHASEN_JE_PORTFOLIO} Phasen, "
                             f"nicht {len(fristen)}")
        if not 0 <= abgegebene_phasen <= len(fristen):
            raise ValueError(f"{abgegebene_phasen} abgegebene Phasen passen nicht "
                             f"zu {len(fristen)} Fristen")
        # Offen heißt: Mindestens eine Phase fehlt noch. Abgegeben, bestanden
        # und nicht bestanden setzen alle drei Phasen voraus.
        if self.ist_offen() != (abgegebene_phasen < PHASEN_JE_PORTFOLIO):
            raise ValueError(f"Status {self.status.anzeige} passt nicht zu "
                             f"{abgegebene_phasen} abgegebenen Phasen")
        self._phasenfristen = fristen
        self._abgegebene_phasen = abgegebene_phasen

    @property
    def phasenfristen(self) -> tuple[date, ...]:
        return tuple(self._phasenfristen)

    @property
    def abgegebene_phasen(self) -> int:
        return self._abgegebene_phasen

    def phase_abgeben(self) -> None:
        """Gibt die nächste Phase ab; nach der dritten ist das Portfolio abgegeben.

        Abgeben lässt sich nur eine Phase, deren Frist eingetragen ist. Sonst
        stünden mehr abgegebene Phasen als Fristen im Portfolio, und eine
        später eingetragene Frist landete bei einer schon abgegebenen Phase.
        """
        if self._status is not Pruefungsstatus.ANGEMELDET:
            raise ValueError("Eine Phase lässt sich nur abgeben, wenn das "
                             f"Portfolio angemeldet ist (Status: {self._status.anzeige})")
        naechste = self._abgegebene_phasen + 1
        if naechste > len(self._phasenfristen):
            raise ValueError(f"Erst die Frist der Phase {naechste} eintragen")
        self._abgegebene_phasen = naechste
        if naechste == PHASEN_JE_PORTFOLIO:
            self._status = Pruefungsstatus.ABGEGEBEN

    def status_setzen(self, status: Pruefungsstatus) -> None:
        """Status "abgegeben" heißt beim Portfolio: die letzte Phase ist abgegeben.

        Von Hand gesetzt gibt er deshalb die dritte Phase ab und ist erst
        möglich, wenn die ersten beiden abgegeben sind. Wird er zurück auf
        geplant oder angemeldet gesetzt, ist die dritte Phase wieder offen.
        """
        offen = (Pruefungsstatus.GEPLANT, Pruefungsstatus.ANGEMELDET)
        if status is Pruefungsstatus.ABGEGEBEN and self._status in offen:
            letzte = PHASEN_JE_PORTFOLIO
            if self._abgegebene_phasen < letzte - 1:
                raise ValueError(f"Abgegeben ist ein Portfolio mit Phase {letzte}; offen ist "
                                 f"noch Phase {self._abgegebene_phasen + 1}")
            self.phase_abgeben()             # prüft Anmeldung und Frist der Phase 3
            return
        wieder_offen = self._status is Pruefungsstatus.ABGEGEBEN and status in offen
        super().status_setzen(status)
        if wieder_offen:
            self._abgegebene_phasen = PHASEN_JE_PORTFOLIO - 1

    def naechster_termin(self) -> date | None:
        return self._termin_oder_ziel(self._gebuchter_termin())

    def _gebuchter_termin(self) -> date | None:
        """Frist der ersten noch nicht abgegebenen Phase."""
        offen = self._phasenfristen[self._abgegebene_phasen:]
        return offen[0] if offen else None

    def naechste_aufgabe(self) -> str:
        return f"Phase {min(self._abgegebene_phasen + 1, PHASEN_JE_PORTFOLIO)} abgeben"

    def note_eintragen(self, note: Decimal, datum: date) -> None:
        """Eine Note gibt es erst, wenn alle drei Phasen abgegeben sind."""
        if self._abgegebene_phasen < PHASEN_JE_PORTFOLIO:
            raise ValueError(f"Erst {self._abgegebene_phasen} von "
                             f"{PHASEN_JE_PORTFOLIO} Phasen sind abgegeben")
        super().note_eintragen(note, datum)

    def _naechste_frist_nr(self) -> int:
        """Phase, deren Frist termin_setzen() setzt (1 bis 3).

        Solange Fristen fehlen, ist es die erste Phase ohne Frist. Stehen alle
        drei fest, ist es die nächste offene Phase; so lässt sich deren Frist
        korrigieren, etwa nach einer Verlängerung.
        """
        if len(self._phasenfristen) < PHASEN_JE_PORTFOLIO:
            return len(self._phasenfristen) + 1
        return self._abgegebene_phasen + 1

    def _termin_eintragen(self, datum: date) -> None:
        """Setzt die Frist der Phase aus _naechste_frist_nr().

        Die Fristen bleiben aufsteigend: Die neue Frist darf nicht vor der
        vorigen Phase und nicht nach der folgenden liegen.
        """
        nr = self._naechste_frist_nr()
        neu = list(self._phasenfristen)
        if nr <= len(neu):
            neu[nr - 1] = datum
        else:
            neu.append(datum)
        if neu != sorted(neu):
            raise ValueError(f"Die Frist {datum:%d.%m.%Y} passt nicht in die "
                             "Reihenfolge der Phasen")
        self._phasenfristen = neu

    def _termine_leeren(self) -> None:
        """Ein neuer Versuch beginnt mit Phase 1 und eigenen Fristen."""
        self._phasenfristen = []
        self._abgegebene_phasen = 0

    def terminart(self) -> str:
        if not self.ist_offen():                # alle Phasen abgegeben oder bewertet
            return "Phasenfrist"
        return f"Frist Phase {self._naechste_frist_nr()}"

    def phasenstand(self) -> str:
        """Kurzbeschreibung für die Oberfläche, z. B. "2 von 3 Phasen abgegeben"."""
        return f"{self._abgegebene_phasen} von {PHASEN_JE_PORTFOLIO} Phasen abgegeben"
