"""Annuaire : administrateurs et destinataires du rapport quotidien.

- Les administrateurs sont fixés dans les paramètres Azure (VEILLE_ADMINS).
- Les destinataires sont gérés par l'administrateur depuis le portail et
  enregistrés dans le stockage (destinataires.json).
"""

from __future__ import annotations

import re
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable

from .config import Parametres
from .storage import Stockage

FICHIER = "destinataires.json"
_RX_EMAIL = re.compile(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[^@\s<>\"',;]{2,}$")


class ErreurAnnuaire(ValueError):
    """Saisie refusée (adresse invalide, doublon…) : le message s'affiche tel quel."""


@dataclass
class Destinataire:
    id: str
    email: str
    nom: str = ""
    fonction: str = ""
    actif: bool = True
    ajoute_le: str = ""
    ajoute_par: str = ""

    @property
    def libelle(self) -> str:
        return self.nom or self.email


def normaliser_email(email: str) -> str:
    return (email or "").strip().lower()


def email_valide(email: str) -> bool:
    return len(email) <= 254 and bool(_RX_EMAIL.match(email))


class Annuaire:
    def __init__(self, stockage: Stockage, parametres: Parametres,
                 horloge: Callable[[], datetime] | None = None):
        self.stockage = stockage
        self.parametres = parametres
        self.horloge = horloge or datetime.now

    # --- lecture ----------------------------------------------------------------------
    def lister(self) -> list[Destinataire]:
        donnees = self.stockage.lire_json(FICHIER)
        if donnees is None:
            return self._initialiser()
        return [Destinataire(**d) for d in donnees]

    def actifs(self) -> list[str]:
        return [d.email for d in self.lister() if d.actif]

    def trouver(self, identifiant: str) -> Destinataire | None:
        return next((d for d in self.lister() if d.id == identifiant), None)

    def est_admin(self, email: str) -> bool:
        return normaliser_email(email) in self.parametres.admins

    def role(self, email: str) -> str | None:
        """« admin », « lecteur » (destinataire actif) ou None (accès refusé)."""
        email = normaliser_email(email)
        if not email:
            return None
        if self.est_admin(email):
            return "admin"
        if email in self.actifs():
            return "lecteur"
        return None

    # --- modifications ------------------------------------------------------------------
    def ajouter(self, email: str, nom: str = "", fonction: str = "", par: str = "") -> Destinataire:
        email = normaliser_email(email)
        nom = " ".join((nom or "").split())[:120]
        fonction = " ".join((fonction or "").split())[:120]
        if not email_valide(email):
            raise ErreurAnnuaire("Cette adresse e-mail n'est pas valide.")
        liste = self.lister()
        if any(d.email == email for d in liste):
            raise ErreurAnnuaire("Cette adresse figure déjà dans la liste des destinataires.")
        nouveau = Destinataire(
            id=secrets.token_hex(6), email=email, nom=nom, fonction=fonction, actif=True,
            ajoute_le=self.horloge().isoformat(timespec="seconds"), ajoute_par=normaliser_email(par),
        )
        self._enregistrer(liste + [nouveau])
        return nouveau

    def changer_statut(self, identifiant: str, actif: bool) -> Destinataire:
        liste = self.lister()
        cible = next((d for d in liste if d.id == identifiant), None)
        if cible is None:
            raise ErreurAnnuaire("Destinataire introuvable.")
        cible.actif = actif
        self._enregistrer(liste)
        return cible

    def retirer(self, identifiant: str) -> Destinataire:
        liste = self.lister()
        cible = next((d for d in liste if d.id == identifiant), None)
        if cible is None:
            raise ErreurAnnuaire("Destinataire introuvable.")
        self._enregistrer([d for d in liste if d.id != identifiant])
        return cible

    # --- interne ------------------------------------------------------------------------
    def _enregistrer(self, liste: list[Destinataire]) -> None:
        self.stockage.ecrire_json(FICHIER, [asdict(d) for d in liste])

    def _initialiser(self) -> list[Destinataire]:
        """Premier démarrage : les administrateurs et les adresses de VEILLE_DESTINATAIRES."""
        maintenant = self.horloge().isoformat(timespec="seconds")
        liste: list[Destinataire] = []
        for email in list(self.parametres.admins) + list(self.parametres.destinataires):
            email = normaliser_email(email)
            if email_valide(email) and all(d.email != email for d in liste):
                liste.append(Destinataire(id=secrets.token_hex(6), email=email, actif=True,
                                          ajoute_le=maintenant, ajoute_par="configuration initiale"))
        self._enregistrer(liste)
        return liste
