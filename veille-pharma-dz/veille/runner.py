"""Vérification quotidienne : sources -> article -> e-mail (ou RAS) -> journal."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Parametres, charger_configuration
from .http import ClientHttp
from .mailer import construire_expediteur
from .models import ErreurSource, ResultatSource
from .render import rendre_alerte, rendre_email
from .sources import construire_source
from .storage import Stockage, ouvrir_stockage
from .summarize import construire_redacteur

journal = logging.getLogger(__name__)


def lire_journal(stockage: Stockage, limite: int = 60) -> list[dict]:
    noms = sorted(stockage.lister("journal/"), reverse=True)[:limite]
    entrees = []
    for nom in noms:
        try:
            entrees.append(stockage.lire_json(nom))
        except Exception:
            journal.warning("Entrée de journal illisible : %s", nom, exc_info=True)
    return [x for x in entrees if x]


def executer(
    parametres: Parametres,
    *,
    http: ClientHttp | None = None,
    stockage: Stockage | None = None,
    expediteur=None,
    redacteur=None,
    maintenant: datetime | None = None,
    declenchement: str = "planifie",
) -> dict:
    debut = time.monotonic()
    http = http or ClientHttp()
    stockage = stockage or ouvrir_stockage(parametres)
    maintenant = maintenant or datetime.now(ZoneInfo(parametres.fuseau))
    jour = maintenant.date()
    identifiant = maintenant.strftime("%Y-%m-%dT%H-%M-%S")
    config = charger_configuration(parametres.fichier_sources)
    etat_global: dict = stockage.lire_json("etat.json", {}) or {}

    # 1. Vérifier chaque source -------------------------------------------------------
    resultats: list[ResultatSource] = []
    for cfg in config.sources:
        if not cfg.actif:
            continue
        try:
            source = construire_source(cfg, http, config)
            resultat = source.executer(etat_global.get(cfg.id), jour)
        except ErreurSource as exc:
            resultat = ResultatSource(cfg.id, cfg.nom, "erreur", str(exc))
        except Exception as exc:
            journal.exception("Erreur inattendue sur la source %s", cfg.id)
            resultat = ResultatSource(cfg.id, cfg.nom, "erreur", f"Erreur inattendue : {exc}")
        journal.info("Source %s : %s – %s", cfg.id, resultat.statut, resultat.detail)
        resultats.append(resultat)

    # 2. Rédiger l'article ------------------------------------------------------------
    trouvailles = [t for r in resultats for t in r.trouvailles]
    article = None
    if trouvailles:
        redacteur = redacteur or construire_redacteur(http, parametres)
        article = redacteur.rediger(trouvailles, jour)
    nb = len(article.elements) if article else 0
    en_erreur = [r for r in resultats if r.statut == "erreur"]
    statut = "NOUVEAUTES" if nb else ("INCOMPLET" if en_erreur else "RAS")

    entree: dict = {
        "id": identifiant,
        "date": maintenant.isoformat(timespec="seconds"),
        "declenchement": declenchement,
        "statut": statut,
        "nb_nouveautes": nb,
        "sources": [{
            "id": r.source_id, "nom": r.source_nom, "statut": r.statut, "detail": r.detail,
            "elements_verifies": r.elements_verifies, "nb_trouvailles": len(r.trouvailles),
        } for r in resultats],
        "elements": [{
            "titre": el.titre, "type": el.trouvaille.type_texte, "source": el.trouvaille.source_nom,
            "url": el.trouvaille.url, "impact": el.impact,
        } for el in (article.elements if article else [])],
        "ecartes": article.ecartes if article else [],
        "mode_redaction": article.mode if article else None,
        "avertissement": article.avertissement if article else None,
        "rapport": None,
        "email": {"envoye": False, "destinataires": [], "erreur": None},
    }

    # 3. Envoyer l'e-mail seulement s'il y a des nouveautés ------------------------------
    email_ok = True
    if nb:
        sujet, html = rendre_email(article, entree, jour, parametres.url_journal)
        entree["rapport"] = f"rapports/{identifiant}.html"
        stockage.ecrire_texte(entree["rapport"], html, "text/html")
        try:
            if not parametres.destinataires:
                raise RuntimeError("Aucun destinataire configuré (paramètre VEILLE_DESTINATAIRES).")
            expediteur = expediteur or construire_expediteur(http, parametres, stockage)
            expediteur.envoyer(parametres.destinataires, sujet, html)
            entree["email"] = {"envoye": True, "destinataires": parametres.destinataires, "erreur": None}
        except Exception as exc:
            journal.exception("Envoi de l'e-mail impossible")
            email_ok = False
            entree["email"] = {"envoye": False, "destinataires": parametres.destinataires, "erreur": str(exc)}
            entree["remarque"] = ("L'e-mail n'a pas pu être envoyé : ces nouveautés seront de nouveau "
                                  "signalées à la prochaine vérification.")

    # 4. Alerte technique si une source n'a pas pu être vérifiée --------------------------
    if (en_erreur or not email_ok) and parametres.alerte_admin:
        try:
            sujet, html = rendre_alerte(entree, jour, parametres.url_journal)
            expediteur = expediteur or construire_expediteur(http, parametres, stockage)
            expediteur.envoyer(parametres.alerte_admin, sujet, html)
        except Exception:
            journal.exception("Alerte technique non envoyée")

    # 5. Mémoriser l'état (sauf si l'e-mail est parti en échec : on réessaiera) ----------
    if email_ok:
        for r in resultats:
            if r.etat is not None:
                etat_global[r.source_id] = r.etat
        stockage.ecrire_json("etat.json", etat_global)

    entree["duree_secondes"] = round(time.monotonic() - debut, 1)
    stockage.ecrire_json(f"journal/{identifiant}.json", entree)
    journal.info("Veille terminée : %s (%s nouveauté(s))", statut, nb)
    return entree
