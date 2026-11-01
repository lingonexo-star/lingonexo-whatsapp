"""Connexion sans mot de passe : lien à usage unique envoyé par e-mail, puis session signée.

- Le lien est valable 15 minutes et ne sert qu'une fois.
- Ouvrir le lien affiche un bouton « Ouvrir ma session » : les antivirus de messagerie
  qui visitent les liens ne peuvent donc pas le consommer à la place de la personne.
- La session est un cookie signé (HMAC-SHA256) valable 12 heures. Le rôle est relu
  à chaque requête : retirer quelqu'un de la liste lui coupe l'accès immédiatement.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

from .storage import Stockage

NOM_COOKIE = "veille_session"
DUREE_SESSION = timedelta(hours=12)
DUREE_LIEN = timedelta(minutes=15)
MAX_DEMANDES_PAR_HEURE = 5


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _b64(octets: bytes) -> str:
    return base64.urlsafe_b64encode(octets).decode().rstrip("=")


def _deb64(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def _empreinte(texte: str) -> str:
    return hashlib.sha256(texte.encode()).hexdigest()


class Sessions:
    def __init__(self, secret: str, horloge: Callable[[], datetime] = _maintenant):
        if not secret:
            raise ValueError("VEILLE_SECRET est obligatoire pour signer les sessions.")
        self.cle = secret.encode()
        self.horloge = horloge

    def _signer(self, charge: str) -> str:
        return hmac.new(self.cle, charge.encode(), hashlib.sha256).hexdigest()

    def creer(self, email: str) -> str:
        expire = int((self.horloge() + DUREE_SESSION).timestamp())
        charge = _b64(json.dumps({"e": email, "x": expire}).encode())
        return f"{charge}.{self._signer(charge)}"

    def lire(self, valeur: str | None) -> str | None:
        """Adresse e-mail de la session, ou None si absente, falsifiée ou expirée."""
        if not valeur or "." not in valeur:
            return None
        charge, signature = valeur.rsplit(".", 1)
        if not hmac.compare_digest(signature, self._signer(charge)):
            return None
        try:
            donnees = json.loads(_deb64(charge))
        except (ValueError, json.JSONDecodeError):
            return None
        if int(donnees.get("x", 0)) < self.horloge().timestamp():
            return None
        return str(donnees.get("e") or "") or None

    def jeton_formulaire(self, valeur: str) -> str:
        """Jeton anti-falsification (CSRF) lié à la session, à placer dans chaque formulaire."""
        return hmac.new(self.cle, f"formulaire|{valeur}".encode(), hashlib.sha256).hexdigest()[:40]

    def verifier_formulaire(self, valeur: str | None, jeton: str | None) -> bool:
        return bool(valeur and jeton) and hmac.compare_digest(self.jeton_formulaire(valeur), jeton)


class LiensConnexion:
    """Liens à usage unique, conservés (empreinte seulement) dans le stockage."""

    def __init__(self, stockage: Stockage, horloge: Callable[[], datetime] = _maintenant):
        self.stockage = stockage
        self.horloge = horloge

    def _nom(self, jeton: str) -> str:
        return f"securite/liens/{_empreinte(jeton)}.json"

    def emettre(self, email: str) -> str:
        jeton = secrets.token_urlsafe(32)
        expire = (self.horloge() + DUREE_LIEN).isoformat()
        self.stockage.ecrire_json(self._nom(jeton), {"email": email, "expire": expire})
        return jeton

    def verifier(self, jeton: str) -> str | None:
        if not jeton or len(jeton) > 100:
            return None
        donnees = self.stockage.lire_json(self._nom(jeton))
        if not donnees:
            return None
        if datetime.fromisoformat(donnees["expire"]) < self.horloge():
            self.stockage.supprimer(self._nom(jeton))
            return None
        return donnees["email"]

    def consommer(self, jeton: str) -> str | None:
        email = self.verifier(jeton)
        if email:
            self.stockage.supprimer(self._nom(jeton))
        return email

    def limite_atteinte(self, email: str) -> bool:
        """Au plus 5 demandes de lien par heure et par adresse."""
        nom = f"securite/demandes/{_empreinte(email)}.json"
        maintenant = self.horloge()
        recentes = [d for d in (self.stockage.lire_json(nom, []) or [])
                    if datetime.fromisoformat(d) > maintenant - timedelta(hours=1)]
        if len(recentes) >= MAX_DEMANDES_PAR_HEURE:
            return True
        self.stockage.ecrire_json(nom, recentes + [maintenant.isoformat()])
        return False
