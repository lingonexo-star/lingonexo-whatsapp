"""Accès réseau avec nouvelles tentatives et messages d'erreur lisibles."""

from __future__ import annotations

import time

import requests

from .models import ErreurSource

AGENT = "VeillePharmaDZ/1.0 (veille reglementaire automatique)"


class ClientHttp:
    def __init__(self, delai: float = 45, essais: int = 3, pause: float = 2.0):
        self.delai = delai
        self.essais = essais
        self.pause = pause
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": AGENT,
            "Accept-Language": "fr,ar;q=0.8,en;q=0.5",
        })

    def requete(self, methode: str, url: str, **options) -> requests.Response:
        delai = options.pop("timeout", self.delai)
        derniere: Exception | None = None
        for essai in range(self.essais):
            try:
                reponse = self.session.request(methode, url, timeout=delai, **options)
                if reponse.status_code >= 500 and essai < self.essais - 1:
                    reponse.close()
                    time.sleep(self.pause * (2 ** essai))
                    continue
                return reponse
            except (requests.ConnectionError, requests.Timeout) as exc:
                derniere = exc
                if essai < self.essais - 1:
                    time.sleep(self.pause * (2 ** essai))
        nom = derniere.__class__.__name__ if derniere else "erreur"
        raise ErreurSource(f"Site injoignable : {url} ({nom})")

    def get(self, url: str, **options) -> requests.Response:
        return self.requete("GET", url, **options)

    def post(self, url: str, **options) -> requests.Response:
        return self.requete("POST", url, **options)

    def get_ok(self, url: str, **options) -> requests.Response:
        reponse = self.get(url, **options)
        if reponse.status_code != 200:
            raise ErreurSource(f"Réponse HTTP {reponse.status_code} pour {url}")
        return reponse

    def est_pdf(self, url: str, codes_absents: tuple[int, ...] = (404, 410)) -> bool:
        """True si l'adresse renvoie un PDF, False si le document n'existe pas.

        Toute autre réponse (site en panne, accès bloqué) lève ErreurSource :
        on ne doit jamais conclure « pas de nouveauté » quand on n'a pas pu vérifier.
        """
        reponse = self.get(url, stream=True)
        try:
            if reponse.status_code in codes_absents:
                return False
            if reponse.status_code != 200:
                raise ErreurSource(f"Réponse HTTP inattendue {reponse.status_code} pour {url}")
            debut = next(reponse.iter_content(chunk_size=8), b"")
            return debut.startswith(b"%PDF")
        finally:
            reponse.close()
