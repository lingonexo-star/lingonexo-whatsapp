"""Stockage de l'état, du journal et des rapports.

- Sur Azure : un conteneur Blob du compte de stockage de la Function App.
- En local (tests) : un dossier sur le disque.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Parametres


class Stockage:
    def lire_texte(self, nom: str) -> str | None:
        raise NotImplementedError

    def ecrire_texte(self, nom: str, contenu: str, type_contenu: str = "text/plain") -> None:
        raise NotImplementedError

    def lister(self, prefixe: str) -> list[str]:
        raise NotImplementedError

    def lire_json(self, nom: str, defaut=None):
        contenu = self.lire_texte(nom)
        return defaut if contenu is None else json.loads(contenu)

    def ecrire_json(self, nom: str, donnees) -> None:
        self.ecrire_texte(nom, json.dumps(donnees, ensure_ascii=False, indent=2), "application/json")


class StockageLocal(Stockage):
    def __init__(self, dossier: str | Path):
        self.dossier = Path(dossier)

    def _chemin(self, nom: str) -> Path:
        chemin = (self.dossier / nom).resolve()
        if self.dossier.resolve() not in chemin.parents:
            raise ValueError(f"Nom de fichier refusé : {nom}")
        return chemin

    def lire_texte(self, nom: str) -> str | None:
        chemin = self._chemin(nom)
        return chemin.read_text(encoding="utf-8") if chemin.exists() else None

    def ecrire_texte(self, nom: str, contenu: str, type_contenu: str = "text/plain") -> None:
        chemin = self._chemin(nom)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding="utf-8")

    def lister(self, prefixe: str) -> list[str]:
        dossier = self._chemin(prefixe.rstrip("/") + "/_").parent
        if not dossier.exists():
            return []
        return sorted(f"{prefixe.rstrip('/')}/{p.name}" for p in dossier.iterdir() if p.is_file())


class StockageBlob(Stockage):
    def __init__(self, conteneur):
        self.conteneur = conteneur

    def lire_texte(self, nom: str) -> str | None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self.conteneur.download_blob(nom).readall().decode("utf-8")
        except ResourceNotFoundError:
            return None

    def ecrire_texte(self, nom: str, contenu: str, type_contenu: str = "text/plain") -> None:
        from azure.storage.blob import ContentSettings

        self.conteneur.upload_blob(
            nom, contenu.encode("utf-8"), overwrite=True,
            content_settings=ContentSettings(content_type=f"{type_contenu}; charset=utf-8"),
        )

    def lister(self, prefixe: str) -> list[str]:
        return sorted(b.name for b in self.conteneur.list_blobs(name_starts_with=prefixe))


def ouvrir_stockage(parametres: Parametres) -> Stockage:
    if parametres.stockage != "azure":
        return StockageLocal(parametres.dossier_donnees)

    from azure.core.exceptions import ResourceExistsError
    from azure.storage.blob import BlobServiceClient

    if parametres.connexion_stockage:
        service = BlobServiceClient.from_connection_string(parametres.connexion_stockage)
    elif parametres.compte_stockage:  # identité managée (Flex Consumption)
        from azure.identity import DefaultAzureCredential

        service = BlobServiceClient(
            f"https://{parametres.compte_stockage}.blob.core.windows.net",
            credential=DefaultAzureCredential(),
        )
    else:
        raise RuntimeError(
            "Stockage Azure non configuré : renseignez AzureWebJobsStorage ou VEILLE_STOCKAGE_CONNEXION.")
    conteneur = service.get_container_client(parametres.conteneur)
    try:
        conteneur.create_container()
    except ResourceExistsError:
        pass
    return StockageBlob(conteneur)
