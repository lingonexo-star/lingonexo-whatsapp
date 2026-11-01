"""Surveillance de sites web : pages d'actualités et flux RSS/Atom.

Principe : on mémorise les liens déjà vus. Chaque matin, les liens nouveaux
sont filtrés par mots-clés ; les pertinents sont ouverts pour en extraire le
contenu, qui servira au résumé.
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from defusedxml import ElementTree
from pypdf import PdfReader

from ..config import ConfigSource, Configuration
from ..http import ClientHttp
from ..models import ErreurSource, ResultatSource, Trouvaille
from ..textutil import couper, recoller

journal = logging.getLogger(__name__)

MAX_LIENS_MEMORISES = 3000
LONGUEUR_MIN_TITRE = 15
_ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass
class Element:
    url: str
    titre: str
    description: str = ""
    date: str = ""


def cle_url(url: str) -> str:
    parties = urlsplit(url.strip())
    hote = parties.netloc.lower().removeprefix("www.")
    chemin = parties.path.rstrip("/") or "/"
    return urlunsplit((parties.scheme.lower(), hote, chemin, parties.query, ""))


def _meme_site(a: str, b: str) -> bool:
    return urlsplit(a).netloc.lower().removeprefix("www.") == urlsplit(b).netloc.lower().removeprefix("www.")


def texte_html(html: str) -> str:
    soupe = BeautifulSoup(html, "html.parser")
    for balise in soupe(["script", "style", "nav", "header", "footer", "form", "noscript"]):
        balise.decompose()
    description = soupe.find("meta", attrs={"name": "description"})
    zone = soupe.find("article") or soupe.find("main") or soupe.body or soupe
    morceaux = []
    if description and description.get("content"):
        morceaux.append(description["content"])
    morceaux.append(zone.get_text(" ", strip=True))
    return recoller(" ".join(morceaux))


def texte_pdf(contenu: bytes, pages: int = 3) -> str:
    lecteur = PdfReader(io.BytesIO(contenu))
    return recoller(" ".join((p.extract_text() or "") for p in lecteur.pages[:pages]))


class SourceSuivie:
    """Base commune : détection des nouveaux éléments et filtrage."""

    type_texte = "Publication"

    def __init__(self, cfg: ConfigSource, http: ClientHttp, config: Configuration):
        self.cfg = cfg
        self.http = http
        self.config = config

    def lister(self) -> list[Element]:
        raise NotImplementedError

    def pertinence(self, element: Element) -> list[str] | None:
        texte = f"{element.titre} {element.description}"
        if self.config.exclusions.correspondances(texte):
            return None
        mots: list[str] = []
        if self.cfg.filtrer:
            mots = self.config.mots_cles.correspondances(texte)
            if not mots:
                return None
        if self.cfg.exige_terme_reglementaire and not self.config.termes_reglementaires.correspondances(texte):
            return None
        return mots

    def lire_detail(self, element: Element) -> str:
        try:
            reponse = self.http.get(element.url)
            if reponse.status_code != 200:
                return ""
            type_contenu = reponse.headers.get("content-type", "").lower()
            if "pdf" in type_contenu or reponse.content[:4] == b"%PDF":
                return couper(texte_pdf(reponse.content), 4000)
            return couper(texte_html(reponse.text), 4000)
        except Exception:  # le détail est un bonus : on garde au moins le titre
            journal.warning("Lecture impossible : %s", element.url, exc_info=True)
            return ""

    def executer(self, etat: dict | None, aujourdhui: date) -> ResultatSource:
        elements = self.lister()
        if len(elements) < self.cfg.min_elements:
            raise ErreurSource(
                f"Seulement {len(elements)} élément(s) trouvé(s) sur {self.cfg.url} : la page a "
                "peut-être changé de structure, ou l'accès est bloqué.")

        etat = dict(etat or {})
        vus = list(etat.get("vus") or [])
        deja_vus = set(vus)
        nouveaux = [e for e in elements if cle_url(e.url) not in deja_vus]
        vus.extend(cle_url(e.url) for e in nouveaux)
        nouvel_etat = {"initialise": True, "vus": vus[-MAX_LIENS_MEMORISES:]}

        if not etat.get("initialise"):
            return ResultatSource(
                self.cfg.id, self.cfg.nom, "initialisation",
                f"Première vérification : {len(elements)} publications existantes enregistrées "
                "comme point de départ. Seules les nouvelles seront signalées.",
                elements_verifies=len(elements), etat=nouvel_etat)

        trouvailles: list[Trouvaille] = []
        for element in nouveaux[: self.cfg.max_nouveautes]:
            mots = self.pertinence(element)
            if mots is None:
                continue
            detail = self.lire_detail(element) if self.cfg.lire_page else ""
            texte = detail or element.description
            trouvailles.append(Trouvaille(
                id=f"{self.cfg.id}-{hashlib.sha1(cle_url(element.url).encode()).hexdigest()[:10]}",
                source_id=self.cfg.id,
                source_nom=self.cfg.nom,
                type_texte="Article de presse" if self.cfg.categorie == "presse" else self.type_texte,
                titre=element.titre,
                url=element.url,
                categorie=self.cfg.categorie,
                reference=f"{self.cfg.nom}" + (f" – {element.date}" if element.date else ""),
                extrait=couper(texte or element.titre, 600),
                texte=couper(f"{element.titre}\n{texte}", 5000),
                mots_cles=mots,
            ))

        return ResultatSource(
            self.cfg.id, self.cfg.nom, "ok",
            f"{len(elements)} publications vérifiées, {len(nouveaux)} nouvelle(s), "
            f"{len(trouvailles)} concernant le secteur.",
            elements_verifies=len(elements), trouvailles=trouvailles, etat=nouvel_etat)


class SourcePage(SourceSuivie):
    """Page web (liste d'actualités, de textes réglementaires…)."""

    def lister(self) -> list[Element]:
        reponse = self.http.get_ok(self.cfg.url)
        base = reponse.url or self.cfg.url
        soupe = BeautifulSoup(reponse.text, "html.parser")
        zones = soupe.select(self.cfg.selecteur) if self.cfg.selecteur else [soupe]
        par_url: dict[str, Element] = {}
        for zone in zones:
            for lien in zone.find_all("a", href=True):
                url = urljoin(base, lien["href"].strip()).split("#")[0]
                if urlsplit(url).scheme not in ("http", "https"):
                    continue
                if self.cfg.meme_domaine and not _meme_site(url, base):
                    continue
                titre = recoller(lien.get_text(" ", strip=True) or lien.get("title", ""))
                if len(titre) < LONGUEUR_MIN_TITRE:
                    continue
                actuel = par_url.get(cle_url(url))
                if actuel is None or len(titre) > len(actuel.titre):
                    par_url[cle_url(url)] = Element(url=url, titre=titre)
        return list(par_url.values())


class SourceRss(SourceSuivie):
    """Flux RSS ou Atom (sites WordPress, Google Actualités…)."""

    def lister(self) -> list[Element]:
        reponse = self.http.get_ok(self.cfg.url)
        try:
            racine = ElementTree.fromstring(reponse.content)
        except Exception as exc:
            raise ErreurSource(f"Flux illisible : {self.cfg.url} ({exc.__class__.__name__})") from exc

        def texte(noeud, nom: str) -> str:
            enfant = noeud.find(nom)
            return (enfant.text or "").strip() if enfant is not None and enfant.text else ""

        elements: list[Element] = []
        for item in racine.iter("item"):
            description = texte(item, "description")
            elements.append(Element(
                url=texte(item, "link"),
                titre=recoller(texte(item, "title")),
                description=recoller(BeautifulSoup(description, "html.parser").get_text(" ")) if description else "",
                date=texte(item, "pubDate"),
            ))
        for entree in racine.iter(f"{_ATOM}entry"):
            lien = entree.find(f"{_ATOM}link")
            resume = texte(entree, f"{_ATOM}summary") or texte(entree, f"{_ATOM}content")
            elements.append(Element(
                url=(lien.get("href") or "").strip() if lien is not None else "",
                titre=recoller(texte(entree, f"{_ATOM}title")),
                description=recoller(BeautifulSoup(resume, "html.parser").get_text(" ")) if resume else "",
                date=texte(entree, f"{_ATOM}updated") or texte(entree, f"{_ATOM}published"),
            ))
        return [e for e in elements if e.url and e.titre]
