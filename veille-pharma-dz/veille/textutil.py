"""Outils texte : normalisation, mots-clés et dates en français."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}
NOMS_MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

# Mot coupé en fin de ligne : « pharma-\nceutique » -> « pharmaceutique ».
_RX_CESURE = re.compile(
    r"(?<=[a-zàâäçéèêëîïôöùûüÿœ])-[ \t]*\n[ \t]*(?=[a-zàâäçéèêëîïôöùûüÿœ])"
)
_RX_DATE = re.compile(
    r"\b(\d{1,2})(?:er)?\s+(" + "|".join(MOIS) + r")\s+(\d{4})\b"
)


def sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def recoller(texte: str) -> str:
    """Recolle les mots coupés et remet le texte sur une seule ligne."""
    texte = _RX_CESURE.sub("", texte or "")
    return re.sub(r"\s+", " ", texte).strip()


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, apostrophes et espaces uniformisés."""
    texte = (texte or "").replace("’", "'").replace(" ", " ")
    texte = _RX_CESURE.sub("", texte)
    texte = sans_accents(texte).lower()
    return re.sub(r"\s+", " ", texte).strip()


def couper(texte: str, limite: int) -> str:
    """Raccourcit un texte proprement (fin de phrase si possible)."""
    texte = (texte or "").strip()
    if len(texte) <= limite:
        return texte
    morceau = texte[:limite]
    fin_phrase = morceau.rfind(". ")
    if fin_phrase > limite * 0.5:
        return morceau[: fin_phrase + 1]
    espace = morceau.rfind(" ")
    return (morceau[:espace] if espace > 0 else morceau).rstrip(",;:") + "…"


class Filtre:
    """Liste de mots-clés insensible aux accents et aux majuscules.

    Une étoile en fin de mot accepte toutes les terminaisons
    (« pharmac* » trouve pharmacie, pharmaceutique, pharmacien…).
    """

    def __init__(self, motifs: list[str] | None):
        self._motifs: list[tuple[str, re.Pattern[str]]] = []
        for brut in motifs or []:
            n = normaliser(str(brut))
            if not n:
                continue
            rx = re.escape(n).replace(r"\*", r"\w*").replace(r"\ ", r"\s+").replace(" ", r"\s+")
            self._motifs.append((str(brut), re.compile(r"(?<!\w)" + rx + r"(?!\w)")))

    def __bool__(self) -> bool:
        return bool(self._motifs)

    def correspondances(self, texte: str) -> list[str]:
        n = normaliser(texte)
        return [libelle for libelle, rx in self._motifs if rx.search(n)]

    def compter(self, texte: str) -> int:
        n = normaliser(texte)
        return sum(len(rx.findall(n)) for _, rx in self._motifs)


def extraire_date(texte: str) -> date | None:
    """Première date grégorienne écrite en toutes lettres (« 21 octobre 2026 »)."""
    for m in _RX_DATE.finditer(normaliser(texte)):
        try:
            return date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1)))
        except ValueError:
            continue
    return None


def date_fr(d: date) -> str:
    jour = "1er" if d.day == 1 else str(d.day)
    return f"{jour} {NOMS_MOIS[d.month - 1]} {d.year}"


def date_longue_fr(d: date) -> str:
    return f"{JOURS[d.weekday()]} {date_fr(d)}"


def pluriel(n: int, singulier: str, pluriel_: str | None = None) -> str:
    return f"{n} {singulier if n <= 1 else (pluriel_ or singulier + 's')}"
