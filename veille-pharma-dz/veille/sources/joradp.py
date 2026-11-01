"""Surveillance du Journal officiel de la République algérienne (JORADP).

Chaque numéro est publié en PDF avec un numéro qui se suit dans l'année.
Chaque matin on vérifie si le numéro suivant existe : si oui, on le télécharge,
on le découpe en textes (lois, décrets, arrêtés…) et on garde ceux qui
concernent l'industrie pharmaceutique.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import date

from pypdf import PdfReader

from ..config import ConfigSource, Configuration
from ..http import ClientHttp
from ..models import ErreurSource, ResultatSource, Trouvaille
from ..textutil import couper, date_fr, extraire_date, normaliser, recoller

journal = logging.getLogger(__name__)

MODELE_URL = "https://www.joradp.dz/FTP/jo-francais/{annee}/F{annee}{numero:03d}.pdf"
MAX_NUMEROS_PAR_EXECUTION = 15

_TYPES = [
    ("Loi organique", r"Loi\s+organique"),
    ("Loi", r"Loi"),
    ("Ordonnance", r"Ordonnance"),
    ("Décret présidentiel", r"D[ée]cret\s+pr[ée]sidentiel"),
    ("Décret exécutif", r"D[ée]cret\s+ex[ée]cutif"),
    ("Décret législatif", r"D[ée]cret\s+l[ée]gislatif"),
    ("Arrêté interministériel", r"Arr[êe]t[ée]\s+interminist[ée]riel"),
    ("Arrêté", r"Arr[êe]t[ée]"),
    ("Décision", r"D[ée]cision"),
]
_RX_DEBUT = re.compile(
    r"^\s*(?:" + "|".join(f"(?P<t{i}>{rx})" for i, (_, rx) in enumerate(_TYPES)) + r")"
    r"\s+(?:[nN]\s*[°º]|du\s)"
)
_RX_ENTETE = re.compile(
    r"^\s*(?:JOURNAL\s+OFFICIEL\s+DE\s+LA\s+R[ÉE]PUBLIQUE.*|\d{1,3})\s*$", re.I
)
_RX_SECTION = re.compile(
    r"^(?:sommaire|lois?|ordonnances?|decrets|arretes,? decisions(?: et avis)?|"
    r"decisions individuelles|avis et communications|annonces.*|"
    r"conventions et accords internationaux)$"
)
_DEBUTS_AUTORITE = (
    "ministere", "presidence de la republique", "premier ministere",
    "services du premier ministre", "banque d'algerie", "cour constitutionnelle",
    "conseil constitutionnel", "cour des comptes", "autorite ",
)
_RX_FIN_TITRE = re.compile(
    r"^(?:[-—–_=.\s]{3,}$|Le\s+Pr[ée]sident\s+de\s+la\s+R[ée]publique|Le\s+Premier\s+ministre|"
    r"Le\s+Chef\s+du\s+Gouvernement|Les?\s+ministres?\b|La\s+ministre\b|"
    r"Le\s+(?:directeur|gouverneur|secr[ée]taire)\b|Vu\b|Apr[èe]s\s+avis|"
    r"Sur\s+(?:le\s+)?rapport|Le\s+Parlement|L['’]Assembl[ée]e|Le\s+Conseil\b|Art(?:icle|\.)\s)"
)
_RX_POINTILLES = re.compile(r"(?:\s*\.){4,}\s*\d*\s*$")
_RX_NUMERO = re.compile(r"n\s*[°º]\s*(\d{1,2}\s*-\s*\d{1,3})", re.I)
_RX_CORRESPONDANT = re.compile(r"correspondant\s+au\s+(\d{1,2}(?:er)?\s+\S+\s+\d{4})", re.I)
_RX_OBJET = re.compile(
    r"\b(?:portant|fixant|relati(?:f|ve)s?|modifiant|compl[ée]tant|abrogeant|d[ée]finissant|"
    r"instituant|d[ée]terminant|pr[ée]cisant|approuvant|autorisant|cr[ée]ant|organisant|"
    r"tendant|accordant|r[ée]glementant|encadrant)\b.*",
    re.I | re.S,
)
_RX_VISAS = re.compile(r"\b(?:Vu|Apr[èe]s\s+avis|Apr[èe]s\s+approbation)\b[^;]{0,1500};", re.S)
_RX_ARTICLE_1 = re.compile(
    r"Article\s+1er\s*\.?\s*[—–-]+\s*(.+?)(?=\s+Art\.?\s*2\s*\.?\s*[—–-]|$)", re.S
)


@dataclass
class Segment:
    type_texte: str
    page: int
    autorite: str
    lignes: list[str] = field(default_factory=list)
    titre: str = ""
    corps: str = ""
    sommaire: bool = False


def extraire_pages(contenu_pdf: bytes) -> list[str]:
    lecteur = PdfReader(io.BytesIO(contenu_pdf))
    return [(page.extract_text() or "") for page in lecteur.pages]


def _majuscules(ligne: str) -> bool:
    lettres = [c for c in ligne if c.isalpha()]
    return len(lettres) >= 6 and all(c.isupper() for c in lettres)


def _finaliser(seg: Segment) -> Segment:
    titre_l: list[str] = []
    corps_l: list[str] = []
    dans_titre = True
    for i, ligne in enumerate(seg.lignes):
        if dans_titre and i > 0 and _RX_FIN_TITRE.match(ligne):
            dans_titre = False
        (titre_l if dans_titre else corps_l).append(ligne)
        if dans_titre and sum(len(x) for x in titre_l) > 900:
            dans_titre = False
    titre = recoller("\n".join(titre_l))
    if _RX_POINTILLES.search(titre):
        seg.sommaire = True
        titre = _RX_POINTILLES.sub("", titre)
    seg.titre = titre.strip().rstrip(" .")
    seg.corps = recoller("\n".join(corps_l))
    return seg


def decouper(pages: list[str]) -> list[Segment]:
    """Découpe le texte d'un numéro du JO en textes individuels."""
    segments: list[Segment] = []
    courant: Segment | None = None
    autorite = ""
    ligne_autorite_precedente = False

    for numero_page, texte in enumerate(pages, start=1):
        for brute in texte.splitlines():
            ligne = brute.strip()
            if not ligne or _RX_ENTETE.match(ligne):
                continue
            m = _RX_DEBUT.match(ligne)
            if m:
                type_texte = next(
                    nom for i, (nom, _) in enumerate(_TYPES) if m.group(f"t{i}")
                )
                courant = Segment(type_texte, numero_page, autorite, [ligne])
                segments.append(courant)
                ligne_autorite_precedente = False
                continue
            if _majuscules(ligne):
                n = normaliser(ligne)
                if _RX_SECTION.match(n):
                    autorite, courant, ligne_autorite_precedente = "", None, False
                    continue
                if n.startswith(_DEBUTS_AUTORITE):
                    autorite, courant, ligne_autorite_precedente = ligne, None, True
                    continue
                if ligne_autorite_precedente:  # intitulé sur deux lignes
                    autorite = f"{autorite} {ligne}"
                    continue
            ligne_autorite_precedente = False
            if courant is not None:
                courant.lignes.append(ligne)

    return [_finaliser(s) for s in segments]


def analyser_titre(titre: str) -> dict:
    numero = _RX_NUMERO.search(titre)
    correspondant = _RX_CORRESPONDANT.search(titre)
    objet = _RX_OBJET.search(titre)
    date_texte = correspondant.group(1) if correspondant else ""
    if not date_texte:
        d = extraire_date(titre)
        date_texte = date_fr(d) if d else ""
    return {
        "numero": re.sub(r"\s", "", numero.group(1)) if numero else "",
        "date_texte": date_texte,
        "objet": objet.group(0).strip() if objet else "",
    }


def dedoublonner(segments: list[Segment]) -> list[Segment]:
    """Le sommaire répète les titres : on garde la version du corps du journal."""
    retenus: dict[tuple, Segment] = {}
    ordre: list[tuple] = []
    for seg in segments:
        infos = analyser_titre(seg.titre)
        cle = (seg.type_texte, infos["numero"]) if infos["numero"] else (
            seg.type_texte, normaliser(seg.titre)[:150])
        actuel = retenus.get(cle)
        if actuel is None:
            retenus[cle] = seg
            ordre.append(cle)
        elif (actuel.sommaire and not seg.sommaire) or (
            actuel.sommaire == seg.sommaire and len(seg.corps) > len(actuel.corps)
        ):
            retenus[cle] = seg
    return [retenus[c] for c in ordre]


def retirer_visas(texte: str) -> str:
    return re.sub(r"\s+", " ", _RX_VISAS.sub(" ", texte)).strip()


def article_premier(corps: str) -> str:
    m = _RX_ARTICLE_1.search(corps)
    return couper(m.group(1).strip(), 700) if m else ""


class SourceJoradp:
    def __init__(self, cfg: ConfigSource, http: ClientHttp, config: Configuration):
        self.cfg = cfg
        self.http = http
        self.config = config
        self.modele_url = cfg.options.get("modele_url") or MODELE_URL
        self.codes_absents = tuple(cfg.options.get("codes_absents") or (404, 410))

    # --- accès au site -------------------------------------------------------
    def url(self, annee: int, numero: int) -> str:
        return self.modele_url.format(annee=annee, numero=numero)

    def existe(self, annee: int, numero: int) -> bool:
        return self.http.est_pdf(self.url(annee, numero), self.codes_absents)

    def trouver_dernier(self, annee: int) -> int:
        """Dernier numéro paru dans l'année (recherche rapide, ~15 requêtes)."""
        if not self.existe(annee, 1):
            return 0
        bas, haut = 1, 2
        while haut <= 512 and self.existe(annee, haut):
            bas, haut = haut, haut * 2
        while haut - bas > 1:
            milieu = (bas + haut) // 2
            if self.existe(annee, milieu):
                bas = milieu
            else:
                haut = milieu
        return bas

    # --- analyse d'un numéro -------------------------------------------------
    def pertinence(self, seg: Segment) -> tuple[list[str], str] | None:
        if self.config.exclusions.correspondances(seg.titre):
            return None
        mots = self.config.mots_cles
        trouves = mots.correspondances(seg.titre) + mots.correspondances(seg.autorite)
        if trouves:
            return sorted(set(trouves)), "forte"
        corps = retirer_visas(seg.corps)
        if mots.compter(corps) >= 3:
            return sorted(set(mots.correspondances(corps))), "faible"
        return None

    def analyser(self, annee: int, numero: int, contenu: bytes) -> list[Trouvaille]:
        url_pdf = self.url(annee, numero)
        pages = extraire_pages(contenu)
        if sum(len(p.strip()) for p in pages) < 200:
            raise ValueError("le PDF ne contient pas de texte lisible")
        date_jo = extraire_date(pages[0][:1500]) if pages else None
        libelle_jo = f"Journal officiel n° {numero} du {date_fr(date_jo)}" if date_jo else (
            f"Journal officiel n° {numero}/{annee}")

        trouvailles: list[Trouvaille] = []
        for seg in dedoublonner(decouper(pages)):
            resultat = self.pertinence(seg)
            if resultat is None:
                continue
            mots_cles, force = resultat
            infos = analyser_titre(seg.titre)
            corps = retirer_visas(seg.corps)
            empreinte = hashlib.sha1(normaliser(seg.titre).encode()).hexdigest()[:8]
            trouvailles.append(Trouvaille(
                id=f"jo-{annee}-{numero:03d}-{empreinte}",
                source_id=self.cfg.id,
                source_nom=self.cfg.nom,
                type_texte=seg.type_texte,
                titre=seg.titre,
                url=f"{url_pdf}#page={seg.page}",
                categorie="officielle",
                reference=f"{libelle_jo} – page {seg.page} du PDF",
                autorite=seg.autorite.capitalize() if seg.autorite.isupper() else seg.autorite,
                date_texte=infos["date_texte"],
                extrait=article_premier(seg.corps) or couper(corps, 600),
                texte=couper(f"{seg.titre}\n{corps}", 5000),
                mots_cles=mots_cles,
                force=force,
            ))
        return trouvailles

    def a_verifier(self, annee: int, numero: int, raison: str) -> Trouvaille:
        return Trouvaille(
            id=f"jo-{annee}-{numero:03d}-manuel",
            source_id=self.cfg.id,
            source_nom=self.cfg.nom,
            type_texte="Journal officiel",
            titre=f"Journal officiel n° {numero}/{annee} : à consulter manuellement",
            url=self.url(annee, numero),
            reference=f"Journal officiel n° {numero}/{annee}",
            extrait=("Ce numéro vient de paraître mais n'a pas pu être analysé automatiquement "
                     f"({raison}). Merci de le parcourir pour vérifier s'il concerne le secteur."),
            a_verifier=True,
        )

    # --- exécution quotidienne -------------------------------------------------
    def executer(self, etat: dict | None, aujourdhui: date) -> ResultatSource:
        etat = dict(etat or {})
        annee, dernier = etat.get("annee"), etat.get("dernier_numero")

        if annee is None or dernier is None:
            trouve = self.trouver_dernier(aujourdhui.year)
            if trouve == 0 and (aujourdhui.month, aujourdhui.day) > (1, 20):
                raise ErreurSource(
                    f"Aucun numéro du Journal officiel trouvé pour {aujourdhui.year} : l'adresse "
                    "des PDF a peut-être changé, ou le site bloque l'accès.")
            rattraper = int(self.cfg.options.get("numeros_a_rattraper") or 0)
            annee, dernier = aujourdhui.year, max(0, trouve - rattraper)
            if rattraper <= 0:
                return ResultatSource(
                    self.cfg.id, self.cfg.nom, "initialisation",
                    f"Première vérification : dernier numéro paru = n° {trouve}/{annee}. "
                    "Chaque nouveau numéro sera désormais analysé.",
                    elements_verifies=1 if trouve else 0,
                    etat={"annee": annee, "dernier_numero": trouve},
                )
        elif dernier > 0 and not self.existe(annee, dernier):
            # Contrôle de bon fonctionnement : le dernier numéro connu doit rester accessible.
            raise ErreurSource(
                f"Le dernier numéro connu (n° {dernier}/{annee}) n'est plus accessible : le site "
                "a peut-être changé d'adresse ou bloque l'accès.")

        trouvailles: list[Trouvaille] = []
        traites: list[str] = []
        problemes: list[str] = []
        while len(traites) < MAX_NUMEROS_PAR_EXECUTION:
            suivant = dernier + 1
            if self.existe(annee, suivant):
                try:
                    contenu = self.http.get_ok(self.url(annee, suivant)).content
                    trouvailles += self.analyser(annee, suivant, contenu)
                except ErreurSource:
                    raise  # site injoignable en cours de route : on réessaiera demain
                except Exception as exc:  # PDF illisible : signalé pour lecture humaine
                    journal.exception("Analyse impossible du JO %s/%s", suivant, annee)
                    problemes.append(f"n° {suivant}/{annee} illisible ({exc})")
                    trouvailles.append(self.a_verifier(annee, suivant, str(exc)))
                traites.append(f"{suivant}/{annee}")
                dernier = suivant
                continue
            if annee < aujourdhui.year:  # changement d'année
                annee, dernier = annee + 1, 0
                continue
            break

        if traites:
            detail = (f"Numéro(s) analysé(s) : {', '.join(traites)}. "
                      f"{len(trouvailles)} texte(s) concernant le secteur.")
        else:
            detail = f"Aucun nouveau numéro depuis le n° {dernier}/{annee}."
        if problemes:
            detail += " Attention : " + "; ".join(problemes) + "."
        return ResultatSource(
            self.cfg.id, self.cfg.nom, "ok", detail,
            elements_verifies=max(1, len(traites)),
            trouvailles=trouvailles,
            etat={"annee": annee, "dernier_numero": dernier},
        )
