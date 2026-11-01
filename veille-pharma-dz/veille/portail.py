"""Portail web : connexion par lien e-mail, administration des destinataires, journal.

Indépendant d'Azure Functions (facile à tester) : function_app.py ne fait que
traduire la requête HTTP en `Requete` et la `Reponse` en réponse HTTP.
"""

from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import parse_qs, quote, urlsplit
from zoneinfo import ZoneInfo

from . import ui
from .annuaire import Annuaire, ErreurAnnuaire, normaliser_email
from .config import Parametres, charger_configuration
from .mailer import construire_expediteur
from .render import rendre_message
from .runner import executer, lire_journal
from .securite import DUREE_SESSION, NOM_COOKIE, LiensConnexion, Sessions
from .storage import Stockage, ouvrir_stockage

journal = logging.getLogger(__name__)
_RX_ID = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$")
_SECRET_LOCAL = secrets.token_hex(32)  # sessions de test locales uniquement
ENTETES_SECURITE = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": ("default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                                "img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"),
}


@dataclass
class Requete:
    methode: str
    chemin: str
    query: dict = field(default_factory=dict)
    formulaire: dict = field(default_factory=dict)
    cookies: dict = field(default_factory=dict)
    url_base: str = ""  # ex. https://veille.azurewebsites.net


@dataclass
class Reponse:
    statut: int = 200
    corps: str = ""
    entetes: dict = field(default_factory=dict)

    @staticmethod
    def html(corps: str, statut: int = 200) -> "Reponse":
        return Reponse(statut, corps, {"Content-Type": "text/html; charset=utf-8"})

    @staticmethod
    def redirection(cible: str) -> "Reponse":
        return Reponse(303, "", {"Location": cible})


def construire_requete(methode: str, url: str, corps: bytes | None, entete_cookie: str | None) -> Requete:
    """Traduit une requête HTTP brute (Azure Functions ou serveur local) en `Requete`."""
    parties = urlsplit(url)
    query = {k: v[0] for k, v in parse_qs(parties.query).items()}
    formulaire = ({k: v[0] for k, v in parse_qs(corps.decode("utf-8", "replace"), keep_blank_values=True).items()}
                  if corps else {})
    return Requete(methode.upper(), parties.path or "/", query, formulaire, lire_cookies(entete_cookie),
                   f"{parties.scheme}://{parties.netloc}")


def lire_cookies(entete: str | None) -> dict:
    cookies = {}
    for morceau in (entete or "").split(";"):
        if "=" in morceau:
            nom, valeur = morceau.strip().split("=", 1)
            cookies[nom] = valeur
    return cookies


class Portail:
    def __init__(self, parametres: Parametres, *, stockage: Stockage | None = None, expediteur=None,
                 horloge: Callable[[], datetime] | None = None, lanceur: Callable[..., dict] | None = None):
        self.p = parametres
        self.stockage = stockage or ouvrir_stockage(parametres)
        self._expediteur = expediteur
        self.horloge = horloge or (lambda: datetime.now(timezone.utc))
        self.lanceur = lanceur or (lambda: executer(self.p, stockage=self.stockage, declenchement="manuel"))
        self.annuaire = Annuaire(self.stockage, parametres, lambda: self.horloge().astimezone(ZoneInfo(parametres.fuseau)))
        self.sessions = Sessions(parametres.secret or _SECRET_LOCAL, self.horloge)
        self.liens = LiensConnexion(self.stockage, self.horloge)

    @property
    def expediteur(self):
        if self._expediteur is None:
            self._expediteur = construire_expediteur(_http(), self.p, self.stockage)
        return self._expediteur

    # --- point d'entrée ---------------------------------------------------------------------
    def traiter(self, req: Requete) -> Reponse:
        try:
            reponse = self._router(req)
        except Exception:
            journal.exception("Erreur du portail sur %s %s", req.methode, req.chemin)
            reponse = Reponse.html(ui.page_erreur("Erreur inattendue", "L'opération n'a pas pu aboutir. "
                                                  "Réessayez dans un instant."), 500)
        reponse.entetes.update(ENTETES_SECURITE)
        return reponse

    def _router(self, req: Requete) -> Reponse:
        chemin = "/" + req.chemin.strip("/")
        methode = req.methode.upper()
        if not self.p.admins:
            return Reponse.html(ui.page_erreur("Configuration incomplète", "Aucun administrateur n'est défini. "
                                               "Renseignez le paramètre VEILLE_ADMINS dans Azure."), 503)

        # Pages publiques (connexion)
        if chemin == "/connexion":
            return self._connexion(req) if methode == "POST" else Reponse.html(
                ui.page_connexion(self.p.organisation, info=ui.MESSAGES["deconnecte"][1]
                                  if req.query.get("msg") == "deconnecte" else ""))
        if chemin == "/connexion/confirmer":
            return self._confirmer(req, methode)

        ctx = self._contexte(req)
        if ctx is None:
            return Reponse.redirection("/connexion")
        if methode == "POST" and not self.sessions.verifier_formulaire(req.cookies.get(NOM_COOKIE), req.formulaire.get("jeton")):
            return Reponse.redirection(f"{chemin if chemin != '/deconnexion' else '/'}?msg=session")
        flash = req.query.get("msg")

        if chemin == "/deconnexion" and methode == "POST":
            reponse = Reponse.redirection("/connexion?msg=deconnecte")
            reponse.entetes["Set-Cookie"] = self._cookie("", 0, req)
            return reponse
        if chemin == "/":
            return Reponse.redirection("/tableau-de-bord" if ctx.role == "admin" else "/journal")
        if chemin == "/journal" and methode == "GET":
            return Reponse.html(ui.page_journal(ctx, flash, lire_journal(self.stockage, 90)))
        if chemin.startswith("/rapports/") and methode == "GET":
            return self._rapport(chemin.removeprefix("/rapports/"), ctx)

        # Pages réservées à l'administrateur
        admin_seulement = {"/tableau-de-bord", "/destinataires", "/destinataires/action", "/sources", "/verification"}
        if chemin in admin_seulement and ctx.role != "admin":
            return Reponse.html(ui.page_erreur("Accès réservé", "Cette page est réservée à l'administrateur.", ctx), 403)
        if chemin == "/tableau-de-bord" and methode == "GET":
            return self._tableau_de_bord(ctx, flash)
        if chemin == "/destinataires":
            if methode == "POST":
                return self._ajouter(req, ctx)
            return Reponse.html(ui.page_destinataires(ctx, flash, self.annuaire.lister(), self.p.admins))
        if chemin == "/destinataires/action" and methode == "POST":
            return self._action_destinataire(req, ctx)
        if chemin == "/sources" and methode == "GET":
            config = charger_configuration(self.p.fichier_sources)
            derniere = next(iter(lire_journal(self.stockage, 1)), None)
            return Reponse.html(ui.page_sources(ctx, config.sources, derniere))
        if chemin == "/verification" and methode == "POST":
            try:
                self.lanceur()
                return Reponse.redirection("/tableau-de-bord?msg=verification")
            except Exception:
                journal.exception("Vérification manuelle en échec")
                return Reponse.redirection("/tableau-de-bord?msg=verification_echec")
        return Reponse.html(ui.page_erreur("Page introuvable", "Cette page n'existe pas.", ctx), 404)

    # --- session ----------------------------------------------------------------------------
    def _contexte(self, req: Requete) -> ui.Contexte | None:
        valeur = req.cookies.get(NOM_COOKIE)
        email = self.sessions.lire(valeur)
        role = self.annuaire.role(email) if email else None
        if not role:
            return None
        return ui.Contexte(email=email, role=role, jeton=self.sessions.jeton_formulaire(valeur),
                           organisation=self.p.organisation)

    def _cookie(self, valeur: str, duree: int, req: Requete) -> str:
        securise = "; Secure" if (req.url_base or self.p.url_publique).startswith("https") else ""
        return f"{NOM_COOKIE}={valeur}; Path=/; Max-Age={duree}; HttpOnly; SameSite=Lax{securise}"

    def _base(self, req: Requete) -> str:
        return self.p.url_publique or req.url_base.rstrip("/")

    def _connexion(self, req: Requete) -> Reponse:
        email = normaliser_email(req.formulaire.get("email", ""))
        if not email or "@" not in email:
            return Reponse.html(ui.page_connexion(self.p.organisation, erreur="Saisissez une adresse e-mail valide.",
                                                  email=email), 400)
        # Même réponse que l'adresse soit connue ou non : on ne révèle pas qui a accès.
        if self.annuaire.role(email) and not self.liens.limite_atteinte(email):
            jeton = self.liens.emettre(email)
            lien = f"{self._base(req)}/connexion/confirmer?lien={quote(jeton)}"
            sujet, html = rendre_message(
                "Votre lien de connexion au portail de veille", "Connexion au portail",
                ["Bonjour,", "Voici votre lien personnel pour accéder au portail de veille réglementaire. "
                 "Il est valable 15 minutes et ne peut servir qu'une seule fois."],
                ("Ouvrir le portail", lien),
                "Si vous n'êtes pas à l'origine de cette demande, ignorez simplement ce message.",
                self.p.organisation)
            try:
                self.expediteur.envoyer([email], sujet, html)
            except Exception:
                journal.exception("Envoi du lien de connexion impossible")
        return Reponse.html(ui.page_lien_envoye(self.p.organisation))

    def _confirmer(self, req: Requete, methode: str) -> Reponse:
        if methode == "GET":
            jeton = req.query.get("lien", "")
            return Reponse.html(ui.page_confirmer(jeton, bool(self.liens.verifier(jeton)), self.p.organisation))
        email = self.liens.consommer(req.formulaire.get("lien", ""))
        if not email or not self.annuaire.role(email):
            return Reponse.html(ui.page_confirmer("", False, self.p.organisation), 400)
        reponse = Reponse.redirection("/")
        reponse.entetes["Set-Cookie"] = self._cookie(self.sessions.creer(email), int(DUREE_SESSION.total_seconds()), req)
        return reponse

    # --- pages ------------------------------------------------------------------------------
    def _tableau_de_bord(self, ctx: ui.Contexte, flash: str | None) -> Reponse:
        entrees = lire_journal(self.stockage, 60)
        maintenant = self.horloge()
        limite = maintenant - timedelta(days=30)
        recentes = []
        nouveautes_30j = 0
        for x in entrees:
            try:
                quand = datetime.fromisoformat(x["date"])
            except (KeyError, ValueError):
                continue
            if quand >= limite:
                nouveautes_30j += x.get("nb_nouveautes", 0)
            for el in x.get("elements", []):
                if len(recentes) < 8:
                    recentes.append({**el, "jour": ui.date_fr(quand.date()), "rapport": x["id"]})
        destinataires = self.annuaire.lister()
        return Reponse.html(ui.page_tableau_de_bord(
            ctx, flash, entrees[0] if entrees else None, prochaine_verification(self.p, maintenant),
            sum(1 for d in destinataires if d.actif), sum(1 for d in destinataires if not d.actif),
            nouveautes_30j, recentes))

    def _rapport(self, identifiant: str, ctx: ui.Contexte) -> Reponse:
        if not _RX_ID.match(identifiant):
            return Reponse.html(ui.page_erreur("Rapport introuvable", "Ce rapport n'existe pas.", ctx), 404)
        contenu = self.stockage.lire_texte(f"rapports/{identifiant}.html")
        if not contenu:
            return Reponse.html(ui.page_erreur("Rapport introuvable", "Ce rapport n'existe pas.", ctx), 404)
        return Reponse.html(ui.envelopper_rapport(contenu))

    def _ajouter(self, req: Requete, ctx: ui.Contexte) -> Reponse:
        f = req.formulaire
        try:
            nouveau = self.annuaire.ajouter(f.get("email", ""), f.get("nom", ""), f.get("fonction", ""), ctx.email)
        except ErreurAnnuaire as exc:
            return Reponse.html(ui.page_destinataires(ctx, None, self.annuaire.lister(), self.p.admins,
                                                      erreur=str(exc), valeurs=f), 400)
        if not f.get("bienvenue"):
            return Reponse.redirection("/destinataires?msg=ajoute")
        try:
            self._envoyer_bienvenue(nouveau.email, nouveau.nom, req)
            return Reponse.redirection("/destinataires?msg=ajoute_bienvenue")
        except Exception:
            journal.exception("Message de bienvenue non envoyé")
            return Reponse.redirection("/destinataires?msg=ajoute_sans_bienvenue")

    def _action_destinataire(self, req: Requete, ctx: ui.Contexte) -> Reponse:
        identifiant, action = req.formulaire.get("id", ""), req.formulaire.get("action", "")
        try:
            if action == "suspendre":
                self.annuaire.changer_statut(identifiant, False)
                return Reponse.redirection("/destinataires?msg=suspendu")
            if action == "reactiver":
                self.annuaire.changer_statut(identifiant, True)
                return Reponse.redirection("/destinataires?msg=reactive")
            if action == "retirer":
                self.annuaire.retirer(identifiant)
                return Reponse.redirection("/destinataires?msg=retire")
            if action == "tester":
                cible = self.annuaire.trouver(identifiant)
                if cible is None:
                    raise ErreurAnnuaire("introuvable")
                try:
                    self._envoyer_test(cible.email, cible.nom)
                    return Reponse.redirection("/destinataires?msg=test_envoye")
                except Exception:
                    journal.exception("Message de test non envoyé")
                    return Reponse.redirection("/destinataires?msg=test_echec")
        except ErreurAnnuaire:
            return Reponse.redirection("/destinataires?msg=introuvable")
        return Reponse.redirection("/destinataires")

    # --- e-mails ------------------------------------------------------------------------------
    def _salutation(self, nom: str) -> str:
        return f"Bonjour {nom}," if nom else "Bonjour,"

    def _envoyer_bienvenue(self, email: str, nom: str, req: Requete) -> None:
        contact = self.p.admins[0]
        sujet, html = rendre_message(
            "Bienvenue dans la veille réglementaire pharmaceutique", "Bienvenue dans la veille réglementaire",
            [self._salutation(nom),
             "Vous êtes désormais destinataire de la veille réglementaire sur l'industrie pharmaceutique en Algérie.",
             "Chaque matin à 7h00, le Journal officiel, les sites des ministères concernés et la presse sont vérifiés. "
             "Lorsqu'un nouveau texte concerne le secteur, vous recevez une note de synthèse avec un résumé et le lien "
             "vers le texte officiel. Les jours sans nouveauté, aucun e-mail n'est envoyé.",
             "Vous pouvez à tout moment consulter le journal des vérifications sur le portail, en vous connectant avec "
             "cette adresse e-mail."],
            ("Accéder au portail", f"{self._base(req)}/connexion"),
            f"Pour toute question ou pour vous désinscrire, contactez l'administrateur : {contact}.",
            self.p.organisation)
        self.expediteur.envoyer([email], sujet, html)

    def _envoyer_test(self, email: str, nom: str) -> None:
        sujet, html = rendre_message(
            "Message de test – veille réglementaire pharmaceutique", "Message de test",
            [self._salutation(nom), "Ce message confirme que les rapports de veille parviennent bien à cette adresse.",
             "Aucune action n'est nécessaire."], None,
            f"Envoyé depuis le portail par l'administrateur ({self.p.admins[0]}).", self.p.organisation)
        self.expediteur.envoyer([email], sujet, html)


def _http():
    from .http import ClientHttp

    return ClientHttp()


def prochaine_verification(p: Parametres, maintenant: datetime) -> datetime | None:
    """Prochaine exécution du minuteur (format Azure « s m h * * * », heure UTC)."""
    morceaux = p.planning.split()
    if len(morceaux) != 6 or not all(m.isdigit() for m in morceaux[:3]) or any(m != "*" for m in morceaux[3:]):
        return None
    _, minute, heure = (int(m) for m in morceaux[:3])
    utc = maintenant.astimezone(timezone.utc)
    cible = utc.replace(hour=heure, minute=minute, second=0, microsecond=0)
    if cible <= utc:
        cible += timedelta(days=1)
    return cible.astimezone(ZoneInfo(p.fuseau))
