"""Sources ajoutées par l'administrateur, en plus de celles de sources.yaml.

L'administrateur donne un nom et une adresse. Avant d'enregistrer, on vérifie que l'adresse
se lit (page web ou flux RSS/Atom) et qu'elle contient des publications. Dès la vérification
suivante, la source est consultée comme les autres : la première fois sert de point de départ,
ensuite seules les nouvelles publications concernant le secteur sont signalées.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from urllib.parse import urlsplit

from .config import ConfigSource, Configuration, Parametres, charger_configuration
from .models import ErreurSource
from .sources import construire_source
from .sources.web import cle_url
from .storage import Stockage

FICHIER = "sources-ajoutees.json"


class ErreurSourceAdmin(ValueError):
    """Ajout ou retrait impossible : le message s'affiche tel quel à l'administrateur."""


def _config_source(entree: dict) -> ConfigSource:
    return ConfigSource(
        id=entree["id"], nom=entree["nom"], type=entree["type"], url=entree["url"], actif=True,
        categorie="officielle", filtrer=True, exige_terme_reglementaire=False, lire_page=True,
        min_elements=1, options={"ajoutee": True, "ajoutee_par": entree.get("ajoutee_par", ""),
                                 "ajoutee_le": entree.get("ajoutee_le", "")})


def lister(stockage: Stockage) -> list[dict]:
    return stockage.lire_json(FICHIER, []) or []


def charger_configuration_complete(p: Parametres, stockage: Stockage) -> Configuration:
    """Sources de base (sources.yaml) + sources ajoutées depuis l'administration."""
    config = charger_configuration(p.fichier_sources)
    config.sources = config.sources + [_config_source(x) for x in lister(stockage)]
    return config


def _deviner_type(http, url: str) -> str:
    reponse = http.get_ok(url)
    type_contenu = reponse.headers.get("content-type", "").lower()
    debut = reponse.content[:600].lstrip().lower()
    if "xml" in type_contenu or debut.startswith(b"<?xml") or b"<rss" in debut or b"<feed" in debut:
        return "rss"
    return "page"


def ajouter(p: Parametres, stockage: Stockage, http, nom: str, url: str, par: str = "",
            maintenant: datetime | None = None) -> tuple[dict, int]:
    """Teste puis enregistre une nouvelle source. Renvoie (source, nombre de publications lues)."""
    nom = " ".join((nom or "").split())[:120]
    url = (url or "").strip()
    if not url:
        raise ErreurSourceAdmin("Indiquez l'adresse du site (par exemple https://www.exemple.dz/actualites).")
    if "://" not in url:
        url = "https://" + url
    parties = urlsplit(url)
    if parties.scheme not in ("http", "https") or "." not in parties.netloc:
        raise ErreurSourceAdmin("Cette adresse n'est pas valide. Elle doit ressembler à https://www.exemple.dz/actualites.")
    nom = nom or parties.netloc.removeprefix("www.")

    config = charger_configuration_complete(p, stockage)
    if any(s.url and cle_url(s.url) == cle_url(url) for s in config.sources):
        raise ErreurSourceAdmin("Cette adresse fait déjà partie des sources surveillées.")

    try:
        type_source = _deviner_type(http, url)
        entree = {"id": "ajout-" + hashlib.sha1(cle_url(url).encode()).hexdigest()[:10], "nom": nom, "url": url,
                  "type": type_source, "ajoutee_par": par,
                  "ajoutee_le": (maintenant or datetime.now()).isoformat(timespec="seconds")}
        elements = construire_source(_config_source(entree), http, config).lister()
    except ErreurSource as exc:
        raise ErreurSourceAdmin(f"Impossible de lire cette adresse : {exc}") from exc
    if not elements:
        raise ErreurSourceAdmin("Aucune publication trouvée à cette adresse. Indiquez plutôt la page qui liste les "
                                "actualités ou les textes réglementaires du site.")

    stockage.ecrire_json(FICHIER, lister(stockage) + [entree])
    return entree, len(elements)


def retirer(stockage: Stockage, p: Parametres, reference: str) -> dict:
    """Retire une source ajoutée, désignée par son adresse ou son nom."""
    reference = (reference or "").strip()
    if not reference:
        raise ErreurSourceAdmin("Indiquez l'adresse (ou le nom) de la source à retirer.")
    ajoutees = lister(stockage)

    def correspond(x: dict) -> bool:
        if x["nom"].lower() == reference.lower():
            return True
        adresse = reference if "://" in reference else "https://" + reference
        return cle_url(x["url"]) == cle_url(adresse)

    cible = next((x for x in ajoutees if correspond(x)), None)
    if cible is None:
        base = charger_configuration(p.fichier_sources).sources
        if any(s.nom.lower() == reference.lower() or (s.url and reference in s.url) for s in base):
            raise ErreurSourceAdmin("Cette source fait partie des sources de base : elle se modifie dans le fichier "
                                    "sources.yaml.")
        raise ErreurSourceAdmin("Aucune source ajoutée ne correspond à cette adresse ou à ce nom.")
    stockage.ecrire_json(FICHIER, [x for x in ajoutees if x["id"] != cible["id"]])
    return cible


def retirer_par_id(stockage: Stockage, identifiant: str) -> dict:
    ajoutees = lister(stockage)
    cible = next((x for x in ajoutees if x["id"] == identifiant), None)
    if cible is None:
        raise ErreurSourceAdmin("Source introuvable.")
    stockage.ecrire_json(FICHIER, [x for x in ajoutees if x["id"] != identifiant])
    return cible


def est_ajoutee(source: ConfigSource) -> bool:
    return bool(source.options.get("ajoutee"))

