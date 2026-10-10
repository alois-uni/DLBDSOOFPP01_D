"""
Reflexionstest 3 - Komposition und Aggregation
==============================================
Leitfrage: Wie lassen sich die Komposition Studiengang-Semester und die
Aggregation Semester-Modul aus Phase 1 in Python unterscheiden?

  1. Beide Beziehungen sind in Python zunaechst nur Referenzen.
  2. Lebensdauer: Ein Teil lebt, solange irgendwer auf ihn verweist.
  3. Komposition per Entwurf: das Ganze erzeugt seine Teile selbst und
     gibt keine veraenderliche Liste heraus.
  4. Aggregation: das Semester bekommt bestehende Module uebergeben.
  5. Luecke im Diagramm der Phase 1: Wem gehoert ein Modul, das noch
     keinem Semester zugeordnet ist?

Die Lebensdauer wird mit weakref beobachtet. Eine schwache Referenz
haelt ihr Objekt nicht am Leben; sie liefert None, sobald es entfernt ist.
"""

from __future__ import annotations

import gc
import weakref


def befund(nr: int, text: str) -> None:
    print(f"Befund {nr}: {text}")


class Modul:
    def __init__(self, kuerzel: str, ects: int) -> None:
        self.kuerzel = kuerzel
        self.ects = ects


class Semester:
    def __init__(self, nummer: int) -> None:
        self.nummer = nummer
        self._module: list[Modul] = []

    def modul_zuordnen(self, modul: Modul) -> None:     # Aggregation
        self._module.append(modul)

    def modul_entfernen(self, modul: Modul) -> None:
        self._module.remove(modul)

    @property
    def module(self) -> tuple[Modul, ...]:
        return tuple(self._module)


class Studiengang:
    def __init__(self, bezeichnung: str) -> None:
        self.bezeichnung = bezeichnung
        self._semester: list[Semester] = []

    def neues_semester(self) -> Semester:                # Komposition
        s = Semester(len(self._semester) + 1)
        self._semester.append(s)
        return s

    @property
    def semester(self) -> tuple[Semester, ...]:
        return tuple(self._semester)


# 1) + 2) Lebensdauer haengt an Referenzen, nicht an der Beziehungsart.
sg = Studiengang("Cyber Security")
s1 = sg.neues_semester()
beobachter = weakref.ref(s1)
del sg
gc.collect()
assert beobachter() is not None
befund(1, "Nach del studiengang lebt Semester 1 weiter, weil die Variable s1 noch "
          "darauf verweist. Python kennt keine Existenzabhaengigkeit, das "
          "Loeschen des Ganzen loescht die Teile nicht automatisch.")

del s1
gc.collect()
assert beobachter() is None
befund(2, "Erst ohne jede Referenz wird das Semester freigegeben; in CPython "
          "geschieht das sofort ueber die Referenzzaehlung.")

# 3) Komposition per Entwurf: kein Zugriff auf die interne Liste.
sg = Studiengang("Cyber Security")
sg.neues_semester()
try:
    sg.semester.append(Semester(99))                    # type: ignore[attr-defined]
    raise AssertionError("Tupel haette unveraenderlich sein sollen")
except AttributeError:
    pass
assert len(sg.semester) == 1
befund(3, "Semester entstehen nur ueber neues_semester(). Die Eigenschaft semester "
          "liefert ein Tupel, von aussen kommt kein fremdes Semester hinein.")

# 4) Aggregation: Modul ueberlebt das Entfernen aus dem Semester.
s = sg.semester[0]
oop = Modul("DLBDSOOFPP01_D", 5)
s.modul_zuordnen(oop)
s.modul_entfernen(oop)
assert oop.ects == 5 and s.module == ()
befund(4, "modul_entfernen() loest nur die Zuordnung, das Modul besteht weiter. "
          "Der Unterschied zur Komposition liegt allein in der Schnittstelle.")

# 5) Die Luecke: ein nicht zugeordnetes Modul gehoert niemandem.
beobachter_modul = weakref.ref(oop)
del oop
gc.collect()
verloren = beobachter_modul() is None
assert verloren
befund(5, "Ein Modul ohne Semester ist ueber den Studiengang nicht erreichbar und "
          "wird freigegeben, sobald die lokale Variable endet. Das Diagramm braucht "
          "einen Besitzer fuer alle Module, also den Modulkatalog am Studiengang.")


# Gegenprobe mit Modulkatalog
class StudiengangMitKatalog(Studiengang):
    def __init__(self, bezeichnung: str) -> None:
        super().__init__(bezeichnung)
        self._module: list[Modul] = []

    def neues_modul(self, kuerzel: str, ects: int) -> Modul:
        m = Modul(kuerzel, ects)
        self._module.append(m)
        return m


sgk = StudiengangMitKatalog("Cyber Security")
m = sgk.neues_modul("DLBDSOOFPP01_D", 5)
beobachter_modul = weakref.ref(m)
del m
gc.collect()
assert beobachter_modul() is not None
befund(6, "Mit Komposition Studiengang-Modul bleibt das nicht zugeordnete Modul "
          "erreichbar; das Semester aggregiert weiterhin nur.")

print("\nAlle Pruefungen bestanden.")
