"""Structures de données partagées."""

from __future__ import annotations

from dataclasses import dataclass, field


class ErreurSource(Exception):
    """Une source n'a pas pu être vérifiée (site injoignable, structure modifiée…)."""


@dataclass
class Trouvaille:
    """Un texte ou une publication détecté(e) comme potentiellement pertinent(e)."""

    id: str
    source_id: str
    source_nom: str
    type_texte: str
    titre: str
    url: str
    categorie: str = "officielle"  # officielle | presse
    reference: str = ""  # ex. « Journal officiel n° 57 du 21 octobre 2026 – page 4 du PDF »
    autorite: str = ""  # ex. « MINISTÈRE DE L'INDUSTRIE PHARMACEUTIQUE »
    date_texte: str = ""
    extrait: str = ""  # court extrait officiel (sert de résumé sans IA)
    texte: str = ""  # texte plus long transmis à l'IA pour le résumé
    mots_cles: list[str] = field(default_factory=list)
    force: str = "forte"  # forte (titre / ministère) | faible (corps du texte seulement)
    a_verifier: bool = False  # document qui n'a pas pu être analysé : toujours signalé


@dataclass
class ResultatSource:
    source_id: str
    source_nom: str
    statut: str  # ok | initialisation | erreur
    detail: str = ""
    elements_verifies: int = 0
    trouvailles: list[Trouvaille] = field(default_factory=list)
    etat: dict | None = None  # nouvel état à enregistrer (None = garder l'ancien)


@dataclass
class ElementArticle:
    trouvaille: Trouvaille
    titre: str
    resume: str
    impact: str = "à évaluer"  # élevé | moyen | faible | à évaluer | à vérifier
    entree_en_vigueur: str = "Non précisée"
    acteurs: str = ""


@dataclass
class Article:
    chapeau: str
    elements: list[ElementArticle]
    ecartes: list[str] = field(default_factory=list)  # titres jugés hors sujet par l'IA
    mode: str = "simple"  # ia | ia-partiel | simple
    avertissement: str | None = None
