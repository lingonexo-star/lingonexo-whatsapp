"""Administration par e-mail : l'administrateur écrit à l'adresse de la veille, la veille répond.

L'objet du message donne la commande, le contenu donne les personnes ou les sites, une ligne chacun :

    Ajouter              sara.benali@labo.dz, Sara Benali, Pharmacien responsable
    Retirer / Suspendre / Réactiver / Test      sara.benali@labo.dz
    Source               https://www.anpp.dz/actualites, ANPP
    Retirer source       https://www.anpp.dz/actualites
    État                 (rien) : dernière vérification, RAS ou nouveautés, sources
    Liste                (rien) : destinataires et sources
    Vérifier             (rien) : lance une vérification tout de suite
    Aide                 (rien) : le mode d'emploi

Sécurité : seuls les messages des administrateurs (VEILLE_ADMINS) sont lus, et seulement s'ils sont
authentifiés par la messagerie (DMARC, DKIM ou SPF alignés sur le domaine de l'expéditeur). Les
autres messages de la boîte ne sont ni lus ni marqués comme lus.
"""

from __future__ import annotations

import email
import imaplib
import logging
import re
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr

from bs4 import BeautifulSoup

from . import sources_admin
from .annuaire import Annuaire
from .config import Parametres
from .mode_github import ErreurAction, realiser
from .render import rendre_message
from .runner import lire_journal
from .storage import Stockage
from .textutil import normaliser, pluriel

journal = logging.getLogger(__name__)
MAX_MESSAGES = 20

# (synonymes acceptés dans l'objet, code de commande) — du plus long au plus court
COMMANDES = [
    (("retirer une source", "retirer source", "supprimer source", "supprimer une source", "enlever source"), "retirer_source"),
    (("ajouter une source", "ajouter source", "nouvelle source", "source", "sources a surveiller"), "source"),
    (("ajouter", "ajout", "inscrire", "nouveau destinataire"), "ajouter"),
    (("retirer", "supprimer", "desinscrire", "enlever"), "retirer"),
    (("suspendre", "pause"), "suspendre"),
    (("reactiver", "reprendre"), "reactiver"),
    (("test", "tester", "essai"), "test"),
    (("etat", "statut", "ras", "situation"), "etat"),
    (("verifier", "verification", "lancer"), "verifier"),
    (("liste", "lister"), "liste"),
    (("aide", "help", "?", "mode d'emploi"), "aide"),
]
ACTIONS = {"ajouter": "Ajouter un destinataire", "retirer": "Retirer un destinataire",
           "suspendre": "Suspendre un destinataire", "reactiver": "Réactiver un destinataire",
           "test": "Envoyer un e-mail de test", "source": "Ajouter une source", "retirer_source": "Retirer une source"}
TITRES = {"ajouter": "Ajout de destinataires", "retirer": "Retrait de destinataires", "suspendre": "Suspension",
          "reactiver": "Réactivation", "test": "E-mail de test", "source": "Ajout de sources",
          "retirer_source": "Retrait de sources", "etat": "État de la veille", "liste": "Destinataires et sources",
          "verifier": "Vérification à la demande", "aide": "Mode d'emploi", "inconnue": "Commande non reconnue"}

_RX_EMAIL = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")
_RX_URL = re.compile(r"(?:https?://|www\.)[^\s,;<>\"]+", re.I)
_FIN_MESSAGE = re.compile(
    r"^(?:--\s*$|_{5,}|-{5,}|>|le .{3,80} a [ée]crit|on .{3,80} wrote|de\s*:|from\s*:|envoy[ée]\s|sent from|"
    r"cordialement|bien [àa] vous|bien cordialement|salutations|regards|best regards)", re.I)

AIDE = [
    "Écrivez à cette adresse : l'objet du message indique ce que vous voulez faire, le contenu indique les personnes "
    "ou les sites, une ligne chacun.",
    "« Ajouter » : une ligne par personne, par exemple « sara.benali@labo.dz, Sara Benali, Pharmacien responsable ». "
    "La personne reçoit un message de bienvenue.",
    "« Retirer », « Suspendre », « Réactiver » ou « Test » : une adresse par ligne.",
    "« Source » : un site à surveiller en plus, par exemple « https://www.anpp.dz/actualites, ANPP ». "
    "« Retirer source » pour l'enlever.",
    "« État » : la dernière vérification (RAS ou nouveautés) et l'état des sources. « Liste » : les destinataires et "
    "les sources. « Vérifier » : lance une vérification tout de suite.",
    "Réponse dans les 30 minutes environ, du dimanche au jeudi entre 7h et 19h (heure d'Alger).",
]


def _texte_entete(valeur: str | None) -> str:
    return str(make_header(decode_header(valeur or ""))).strip()


def identifier(sujet: str) -> tuple[str, str]:
    """Commande et reste de l'objet (« Ajouter sara@x.dz » → (« ajouter », « sara@x.dz »))."""
    s = re.sub(r"^\s*((re|tr|fw|fwd|réf)\s*:\s*)+", "", sujet or "", flags=re.I).strip()
    n = normaliser(s)
    for synonymes, code in COMMANDES:
        for mot in synonymes:
            if n == mot or n.startswith(mot + " ") or n.startswith(mot + ":"):
                return code, s[len(mot):].lstrip(" :").strip()
    return "inconnue", s


def corps_texte(msg: Message) -> str:
    texte, html = "", ""
    for partie in msg.walk() if msg.is_multipart() else [msg]:
        if partie.get_content_maintype() == "multipart" or partie.get_filename():
            continue
        try:
            contenu = partie.get_payload(decode=True) or b""
            contenu = contenu.decode(partie.get_content_charset() or "utf-8", errors="replace")
        except (LookupError, AttributeError):
            continue
        if partie.get_content_type() == "text/plain" and not texte:
            texte = contenu
        elif partie.get_content_type() == "text/html" and not html:
            html = BeautifulSoup(contenu, "html.parser").get_text("\n")
    return texte or html


def lignes_utiles(corps: str) -> list[str]:
    """Lignes du message, sans la signature ni le message cité."""
    lignes = []
    for brute in (corps or "").splitlines():
        ligne = brute.strip()
        if _FIN_MESSAGE.match(ligne):
            break
        if ligne:
            lignes.append(ligne)
    return lignes[:50]


def authentifie(msg: Message, adresse: str) -> bool:
    """Le message vient-il vraiment de cette adresse ? (contrôles ajoutés par la messagerie à la réception)"""
    domaine = adresse.rsplit("@", 1)[-1].lower()
    resultats = " ".join(msg.get_all("Authentication-Results") or []).lower()
    if not resultats:
        return False

    def aligne(d: str) -> bool:
        d = d.strip(";").lower()
        return d == domaine or d.endswith("." + domaine) or domaine.endswith("." + d)

    if any(aligne(d) for d in re.findall(r"dmarc=pass[^;]*?header\.from=([\w.-]+)", resultats)):
        return True
    if any(aligne(d) for d in re.findall(r"dkim=pass[^;]*?header\.(?:i|d)=@?([\w.-]+)", resultats)):
        return True
    return any(aligne(d.rsplit("@", 1)[-1]) for d in re.findall(r"spf=pass[^;]*?smtp\.mailfrom=([\w.@+-]+)", resultats))


def _decouper(ligne: str) -> list[str]:
    return [x.strip(" .") for x in re.split(r"[,;|\t]", ligne) if x.strip(" .")]


def executer_commande(p: Parametres, code: str, reste: str, lignes: list[str], admin: str, stockage: Stockage,
                      expediteur, http=None, lanceur=None) -> list[str]:
    """Exécute la commande et renvoie les lignes de la réponse."""
    if code == "aide":
        return AIDE
    if code == "inconnue":
        return ["Je n'ai pas reconnu la commande indiquée dans l'objet du message."] + AIDE
    if code == "etat":
        return etat(p, stockage)
    if code == "liste":
        return liste(p, stockage)
    if code == "verifier":
        return [realiser(p, "Lancer une vérification", stockage=stockage, expediteur=expediteur, par=admin,
                         lanceur=lanceur)]

    entrees = ([reste] if reste else []) + lignes
    resultats = []
    for ligne in entrees:
        try:
            if code in ("source", "retirer_source"):
                url = _RX_URL.search(ligne)
                if code == "source" and not url:
                    continue
                nom = ", ".join(x for x in _decouper(_RX_URL.sub("", ligne)) if x)
                message = realiser(p, ACTIONS[code], nom=nom, adresse=url.group(0) if url else ligne,
                                   stockage=stockage, http=http, par=admin)
            else:
                adresse = _RX_EMAIL.search(ligne)
                if not adresse:
                    continue
                if adresse.group(0).lower() == admin and code == "ajouter":
                    continue  # adresse de l'administrateur lui-même (souvent dans sa signature)
                autres = [x for x in _decouper(ligne.replace(adresse.group(0), "")) if x]
                message = realiser(p, ACTIONS[code], email=adresse.group(0),
                                   nom=autres[0] if autres else "", fonction=autres[1] if len(autres) > 1 else "",
                                   bienvenue=True, par=admin, stockage=stockage, expediteur=expediteur)
            resultats.append(f"✓ {message}")
        except ErreurAction as exc:
            resultats.append(f"✗ {ligne} : {exc}")
    if not resultats:
        exemple = ("https://www.exemple.dz/actualites, Nom du site" if code in ("source", "retirer_source")
                   else "prenom.nom@entreprise.dz, Prénom Nom, Fonction")
        return [f"Je n'ai trouvé aucune {'adresse de site' if 'source' in code else 'adresse e-mail'} dans votre "
                f"message. Mettez une ligne par élément, par exemple : « {exemple} »."]
    return resultats


def etat(p: Parametres, stockage: Stockage) -> list[str]:
    entrees = lire_journal(stockage, 30)
    if not entrees:
        return ["Aucune vérification n'a encore eu lieu."]
    d = entrees[0]
    from .mode_github import _quand, _statut  # mise en forme commune avec le tableau de bord
    sources = d.get("sources", [])
    ok = sum(1 for s in sources if s["statut"] != "erreur")
    lignes = [f"Dernière vérification : {_statut(d)} — {_quand(d.get('date'))}.",
              f"Sources vérifiées : {ok} sur {len(sources)}."]
    if d.get("statut") == "RAS":
        lignes.append("RAS : toutes les sources ont été vérifiées et il n'y a aucune nouveauté.")
    lignes += [f"{'✓' if s['statut'] != 'erreur' else '✗'} {s['nom']} — {s['detail']}" for s in sources]
    historique = ", ".join(f"{_quand(x.get('date')).split(' à ')[0]} : {_statut(x)}" for x in entrees[1:6])
    if historique:
        lignes.append(f"Jours précédents : {historique}.")
    lignes.append(f"Destinataires actifs : {len(Annuaire(stockage, p).actifs())}.")
    return lignes


def liste(p: Parametres, stockage: Stockage) -> list[str]:
    destinataires = Annuaire(stockage, p).lister()
    lignes = [f"Destinataires ({pluriel(sum(1 for d in destinataires if d.actif), 'actif')}) :"]
    lignes += [f"{'•' if d.actif else '◦ (suspendu)'} {d.nom + ' — ' if d.nom else ''}{d.email}"
               f"{' — ' + d.fonction if d.fonction else ''}" for d in destinataires]
    lignes.append("Sources surveillées :")
    for src in sources_admin.charger_configuration_complete(p, stockage).sources:
        if src.actif:
            ou = "Journal officiel" if src.type == "joradp" else ("Google Actualités" if src.type == "google_news" else src.url)
            lignes.append(f"• {src.nom} — {ou}{' (ajoutée)' if src.options.get('ajoutee') else ''}")
    return lignes


def traiter(p: Parametres, msg: Message, stockage: Stockage, expediteur, http=None, lanceur=None) -> bool:
    """Traite un message. Renvoie True s'il venait d'un administrateur authentifié (et a reçu une réponse)."""
    _, adresse = parseaddr(_texte_entete(msg.get("From")))
    adresse = adresse.lower()
    if adresse not in p.admins or msg.get("X-Veille-Reglementaire"):
        return False
    if not authentifie(msg, adresse):
        journal.warning("Message de %s ignoré : authentification absente ou en échec", adresse)
        return False
    sujet = _texte_entete(msg.get("Subject"))
    code, reste = identifier(sujet)
    try:
        lignes = executer_commande(p, code, reste, lignes_utiles(corps_texte(msg)), adresse, stockage, expediteur,
                                   http, lanceur)
    except Exception as exc:  # la réponse doit partir quoi qu'il arrive
        journal.exception("Commande %s en échec", code)
        lignes = [f"La commande n'a pas pu aboutir : {exc}"]
    reponse_sujet, html = rendre_message(f"Re: {sujet}" if sujet else "Veille réglementaire",
                                         TITRES.get(code, "Veille réglementaire"), lignes, None,
                                         "Pour la liste des commandes, envoyez un message avec l'objet « Aide ».",
                                         p.organisation)
    expediteur.envoyer([adresse], reponse_sujet, html)
    return True


def relever(p: Parametres, stockage: Stockage, expediteur, imap_fabrique=None, http=None) -> int:
    """Lit les messages non lus des administrateurs, exécute les commandes, répond. Renvoie le nombre traité."""
    if not p.admins:
        return 0
    imap = (imap_fabrique or (lambda: imaplib.IMAP4_SSL(p.imap_hote or "imap.gmail.com")))()
    imap.login(p.smtp_utilisateur, p.smtp_mot_de_passe)
    try:
        imap.select("INBOX")
        numeros: list[bytes] = []
        for admin in p.admins:
            statut, donnees = imap.search(None, "UNSEEN", "FROM", f'"{admin}"')
            if statut == "OK" and donnees and donnees[0]:
                numeros += [n for n in donnees[0].split() if n not in numeros]
        traites = 0
        for numero in sorted(numeros, key=int)[:MAX_MESSAGES]:
            statut, donnees = imap.fetch(numero, "(BODY.PEEK[])")
            if statut != "OK" or not donnees or not isinstance(donnees[0], tuple):
                continue
            msg = email.message_from_bytes(donnees[0][1])
            if msg.get("X-Veille-Reglementaire"):
                continue  # note ou réponse envoyée par la veille : laissée intacte dans la boîte
            if traiter(p, msg, stockage, expediteur, http):
                traites += 1
            imap.store(numero, "+FLAGS", "\\Seen")
        return traites
    finally:
        try:
            imap.logout()
        except Exception:
            pass
