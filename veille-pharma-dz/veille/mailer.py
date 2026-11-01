"""Envoi des e-mails.

- acs     : service d'e-mail d'Azure (Azure Communication Services). Ne dépend d'aucune
            messagerie d'entreprise : c'est le mode installé par installer.sh.
- graph   : Microsoft 365 / Outlook d'une entreprise, via Microsoft Graph
- smtp    : n'importe quel serveur SMTP (Gmail avec mot de passe d'application, etc.)
- fichier : pas d'envoi, le message est enregistré (tests)

Chaque destinataire reçoit son propre message : personne ne voit les adresses des autres.
"""

from __future__ import annotations

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from urllib.parse import quote

from .config import Parametres
from .http import ClientHttp
from .storage import Stockage


class ExpediteurGraph:
    def __init__(self, http: ClientHttp, p: Parametres):
        manquants = [n for n, v in {
            "GRAPH_TENANT_ID": p.graph_tenant, "GRAPH_CLIENT_ID": p.graph_client_id,
            "GRAPH_CLIENT_SECRET": p.graph_secret, "GRAPH_EXPEDITEUR": p.graph_expediteur,
        }.items() if not v]
        if manquants:
            raise RuntimeError("Paramètres e-mail manquants : " + ", ".join(manquants))
        self.http = http
        self.p = p

    def _jeton(self) -> str:
        reponse = self.http.post(
            f"https://login.microsoftonline.com/{self.p.graph_tenant}/oauth2/v2.0/token",
            data={
                "client_id": self.p.graph_client_id,
                "client_secret": self.p.graph_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
        )
        if reponse.status_code != 200:
            raise RuntimeError(f"Connexion Microsoft 365 refusée ({reponse.status_code}) : {reponse.text[:300]}")
        return reponse.json()["access_token"]

    def envoyer(self, destinataires: list[str], sujet: str, html: str) -> None:
        jeton = self._jeton()
        for adresse in destinataires:
            reponse = self.http.post(
                f"https://graph.microsoft.com/v1.0/users/{quote(self.p.graph_expediteur)}/sendMail",
                headers={"Authorization": f"Bearer {jeton}"},
                json={
                    "message": {
                        "subject": sujet,
                        "body": {"contentType": "HTML", "content": html},
                        "toRecipients": [{"emailAddress": {"address": adresse}}],
                    },
                    "saveToSentItems": True,
                },
            )
            if reponse.status_code != 202:
                raise RuntimeError(f"Envoi refusé par Microsoft 365 ({reponse.status_code}) : {reponse.text[:300]}")


class ExpediteurSmtp:
    def __init__(self, p: Parametres):
        if not (p.smtp_hote and p.smtp_expediteur):
            raise RuntimeError("Paramètres e-mail manquants : SMTP_HOTE et SMTP_EXPEDITEUR")
        self.p = p

    def envoyer(self, destinataires: list[str], sujet: str, html: str) -> None:
        with smtplib.SMTP(self.p.smtp_hote, self.p.smtp_port, timeout=60) as serveur:
            serveur.starttls()
            if self.p.smtp_utilisateur:
                serveur.login(self.p.smtp_utilisateur, self.p.smtp_mot_de_passe)
            for adresse in destinataires:
                message = MIMEMultipart("alternative")
                message["Subject"] = sujet
                message["From"] = formataddr((self.p.smtp_nom, self.p.smtp_expediteur))
                message["To"] = adresse
                message.attach(MIMEText(html, "html", "utf-8"))
                serveur.sendmail(self.p.smtp_expediteur, [adresse], message.as_string())


class ExpediteurAcs:
    """Service d'e-mail d'Azure (Azure Communication Services)."""

    def __init__(self, p: Parametres, client=None):
        if not (p.acs_connexion and p.acs_expediteur):
            raise RuntimeError("Paramètres e-mail manquants : ACS_CONNEXION et ACS_EXPEDITEUR")
        if client is None:
            from azure.communication.email import EmailClient

            client = EmailClient.from_connection_string(p.acs_connexion)
        self.client = client
        self.expediteur = p.acs_expediteur

    def envoyer(self, destinataires: list[str], sujet: str, html: str) -> None:
        for adresse in destinataires:
            resultat = self.client.begin_send({
                "senderAddress": self.expediteur,
                "recipients": {"to": [{"address": adresse}]},
                "content": {"subject": sujet, "html": html},
            }).result()
            statut = (resultat or {}).get("status")
            if statut and statut.lower() != "succeeded":
                raise RuntimeError(f"Envoi refusé par Azure ({statut}) : {(resultat or {}).get('error')}")


class ExpediteurFichier:
    """Enregistre le message au lieu de l'envoyer (essais)."""

    def __init__(self, stockage: Stockage):
        self.stockage = stockage
        self.envoyes: list[dict] = []

    def envoyer(self, destinataires: list[str], sujet: str, html: str) -> None:
        horodatage = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
        entete = f"<!-- A : {', '.join(destinataires)}\n     Objet : {sujet} -->\n"
        self.stockage.ecrire_texte(f"boite_envoi/{horodatage}.html", entete + html, "text/html")
        self.envoyes.append({"destinataires": destinataires, "sujet": sujet, "html": html})


def construire_expediteur(http: ClientHttp, p: Parametres, stockage: Stockage):
    if p.mode_email == "acs":
        return ExpediteurAcs(p)
    if p.mode_email == "graph":
        return ExpediteurGraph(http, p)
    if p.mode_email == "smtp":
        return ExpediteurSmtp(p)
    if p.mode_email == "fichier":
        return ExpediteurFichier(stockage)
    raise RuntimeError(f"VEILLE_MODE_EMAIL inconnu : {p.mode_email} (acs, graph, smtp ou fichier)")
