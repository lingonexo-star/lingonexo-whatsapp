"""Charte graphique YoVendoMás : couleurs, typographie et logos (fichiers PNG de ce dossier).

Couleurs relevées sur le logo officiel :
- Nuit    #04050A  fond sombre de la marque
- Encre   #0B1220  texte foncé sur fond clair
- Blanc   #EEF2F6  logo et texte sur fond sombre
- Menthe  #36EABA  → Turquoise #3CD2DE → Azur #42B4FC : dégradé d'accent (encoche du « Y », accent du « á »)
- Azur profond #0B6FB8 : liens et accents lisibles sur fond clair (azur assombri pour le contraste)
Typographie : sans-serif géométrique (Outfit pour le web), repli Segoe UI / Arial.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

MARQUE = "YoVendoMás"
SITE = "yovendomas.com"
PRODUIT = "Veille réglementaire"
NUIT = "#04050A"
ENCRE = "#0B1220"
BLANC = "#EEF2F6"
MENTHE = "#36EABA"
TURQUOISE = "#3CD2DE"
AZUR = "#42B4FC"
AZUR_PROFOND = "#0B6FB8"
POLICE_WEB = "Outfit"

DOSSIER = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def image_data(nom: str) -> str:
    """Image du dossier marque en data URI (pour les pages du portail)."""
    return "data:image/png;base64," + base64.b64encode((DOSSIER / nom).read_bytes()).decode()
