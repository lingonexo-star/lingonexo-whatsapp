"""Paramètres (variables d'environnement) et configuration des sources (sources.yaml)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

import yaml

from .textutil import Filtre

RACINE = Path(__file__).resolve().parent.parent
TYPES_SOURCES = {"joradp", "page", "rss", "google_news"}


@dataclass
class ConfigSource:
    id: str
    nom: str
    type: str
    url: str = ""
    actif: bool = True
    categorie: str = "officielle"
    filtrer: bool = True  # appliquer les mots-clés pharmaceutiques
    exige_terme_reglementaire: bool = False  # exiger aussi « décret », « arrêté »…
    lire_page: bool = True  # ouvrir chaque nouvelle publication pour la résumer
    selecteur: str | None = None  # partie de la page à surveiller (sélecteur CSS)
    meme_domaine: bool = True
    min_elements: int = 3  # en dessous : la page a probablement changé -> erreur
    max_nouveautes: int = 25
    options: dict = field(default_factory=dict)


@dataclass
class Configuration:
    mots_cles: Filtre
    termes_reglementaires: Filtre
    exclusions: Filtre
    sources: list[ConfigSource]


_CHAMPS = {
    "id", "nom", "type", "url", "actif", "categorie", "filtrer", "exige_terme_reglementaire",
    "lire_page", "selecteur", "meme_domaine", "min_elements", "max_nouveautes",
}


def charger_configuration(chemin: str | Path) -> Configuration:
    with open(chemin, encoding="utf-8") as fichier:
        brut = yaml.safe_load(fichier) or {}

    sources: list[ConfigSource] = []
    ids: set[str] = set()
    for entree in brut.get("sources") or []:
        connus = {k: v for k, v in entree.items() if k in _CHAMPS}
        options = {k: v for k, v in entree.items() if k not in _CHAMPS}
        src = ConfigSource(**connus, options=options)
        if src.type not in TYPES_SOURCES:
            raise ValueError(f"Source « {src.id} » : type inconnu « {src.type} »")
        if src.id in ids:
            raise ValueError(f"Identifiant de source en double : « {src.id} »")
        ids.add(src.id)
        if src.type == "google_news":
            requete = options.get("requete", "")
            src.url = "https://news.google.com/rss/search?" + urlencode(
                {"q": requete, "hl": "fr", "gl": "DZ", "ceid": "DZ:fr"}
            )
            src.categorie = "presse"
            src.meme_domaine = False
            src.lire_page = False
            if "min_elements" not in entree:
                src.min_elements = 0
        elif src.type == "rss" and "min_elements" not in entree:
            src.min_elements = 1
        sources.append(src)

    return Configuration(
        mots_cles=Filtre(brut.get("mots_cles")),
        termes_reglementaires=Filtre(brut.get("termes_reglementaires")),
        exclusions=Filtre(brut.get("exclusions")),
        sources=sources,
    )


def _liste(valeur: str | None) -> list[str]:
    return [v for v in re.split(r"[,;\s]+", valeur or "") if v]


@dataclass
class Parametres:
    destinataires: list[str]
    alerte_admin: list[str]
    mode_email: str  # acs | graph | smtp | fichier
    acs_connexion: str  # Azure Communication Services (e-mail)
    acs_expediteur: str
    graph_tenant: str
    graph_client_id: str
    graph_secret: str
    graph_expediteur: str
    smtp_hote: str
    smtp_port: int
    smtp_utilisateur: str
    smtp_mot_de_passe: str
    smtp_expediteur: str
    smtp_nom: str  # nom affiché de l'expéditeur
    aoai_endpoint: str
    aoai_cle: str
    aoai_deploiement: str
    aoai_version: str
    ia_url: str  # IA compatible OpenAI (ex. offre gratuite Gemini) : adresse de l'API
    ia_cle: str
    ia_modele: str
    stockage: str  # azure | local
    dossier_donnees: str
    connexion_stockage: str
    compte_stockage: str
    conteneur: str
    fichier_sources: str
    fuseau: str
    url_journal: str
    admins: list[str]  # adresses des administrateurs (VEILLE_ADMINS)
    secret: str  # clé de signature des sessions (VEILLE_SECRET)
    url_publique: str  # adresse du portail, ex. https://veille-pharma.azurewebsites.net
    organisation: str  # nom affiché dans le portail et les e-mails
    planning: str  # expression du minuteur Azure (VEILLE_PLANNING)

    @property
    def ia_active(self) -> bool:
        return bool(self.aoai_endpoint and self.aoai_cle and self.aoai_deploiement) or bool(self.ia_url and self.ia_cle)


def charger_parametres(env: dict | None = None) -> Parametres:
    env = os.environ if env is None else env
    g = lambda nom, defaut="": (env.get(nom) or defaut).strip()  # noqa: E731

    dans_azure = bool(env.get("WEBSITE_SITE_NAME"))
    connexion = g("VEILLE_STOCKAGE_CONNEXION") or g("AzureWebJobsStorage")
    if connexion == "UseDevelopmentStorage=true" and not dans_azure:
        connexion = ""

    admins = [a.lower() for a in _liste(g("VEILLE_ADMINS"))]
    url_publique = g("VEILLE_URL_PUBLIQUE").rstrip("/")
    return Parametres(
        destinataires=[d.lower() for d in _liste(g("VEILLE_DESTINATAIRES"))],
        alerte_admin=_liste(g("VEILLE_ALERTE_ADMIN")) or admins,
        mode_email=g("VEILLE_MODE_EMAIL", ("acs" if g("ACS_CONNEXION") else "graph") if dans_azure else "fichier").lower(),
        acs_connexion=g("ACS_CONNEXION"),
        acs_expediteur=g("ACS_EXPEDITEUR"),
        graph_tenant=g("GRAPH_TENANT_ID"),
        graph_client_id=g("GRAPH_CLIENT_ID"),
        graph_secret=g("GRAPH_CLIENT_SECRET"),
        graph_expediteur=g("GRAPH_EXPEDITEUR"),
        smtp_hote=g("SMTP_HOTE"),
        smtp_port=int(g("SMTP_PORT", "587")),
        smtp_utilisateur=g("SMTP_UTILISATEUR"),
        smtp_mot_de_passe=g("SMTP_MOT_DE_PASSE"),
        smtp_expediteur=g("SMTP_EXPEDITEUR"),
        smtp_nom=g("SMTP_NOM_EXPEDITEUR", "Veille réglementaire"),
        aoai_endpoint=g("AZURE_OPENAI_ENDPOINT"),
        aoai_cle=g("AZURE_OPENAI_API_KEY"),
        aoai_deploiement=g("AZURE_OPENAI_DEPLOYMENT"),
        aoai_version=g("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        ia_url=g("IA_URL"),
        ia_cle=g("IA_CLE"),
        ia_modele=g("IA_MODELE"),
        stockage=g("VEILLE_STOCKAGE", "azure" if dans_azure else "local").lower(),
        dossier_donnees=g("VEILLE_DOSSIER_DONNEES", str(RACINE / "donnees")),
        connexion_stockage=connexion,
        compte_stockage=g("AzureWebJobsStorage__accountName"),
        conteneur=g("VEILLE_CONTENEUR", "veille-pharma"),
        fichier_sources=g("VEILLE_SOURCES", str(RACINE / "sources.yaml")),
        fuseau=g("VEILLE_FUSEAU", "Africa/Algiers"),
        url_journal=g("VEILLE_URL_JOURNAL") or (f"{url_publique}/journal" if url_publique else ""),
        admins=admins,
        secret=g("VEILLE_SECRET"),
        url_publique=url_publique,
        organisation=g("VEILLE_ORGANISATION"),
        planning=g("VEILLE_PLANNING", "0 0 6 * * *"),
    )
