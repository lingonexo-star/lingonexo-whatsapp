#!/usr/bin/env bash
# Prépare veille-pharma-github.zip : les fichiers à déposer à la racine d'un dépôt GitHub privé.
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
SORTIE="${1:-$ICI/veille-pharma-github.zip}"
TMP="$(mktemp -d)"
DOSSIER="$TMP/veille-pharma"
mkdir -p "$DOSSIER"
cp -r "$ICI/.github" "$ICI/veille" "$ICI/sources.yaml" "$ICI/requirements-github.txt" "$ICI/.gitignore" "$DOSSIER/"
cp "$ICI/GUIDE-GRATUIT.md" "$DOSSIER/DOCUMENTATION.md"
find "$DOSSIER" -name __pycache__ -prune -exec rm -rf {} +
# Page d'accueil de départ (remplacée par le vrai tableau de bord après la première vérification)
(cd "$ICI" && python3 - "$DOSSIER/README.md" <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from veille.config import charger_configuration
from veille.mode_github import rendre_tableau_de_bord
page = rendre_tableau_de_bord([], [], charger_configuration("sources.yaml").sources, "../../actions",
                              "suivi", datetime.now(ZoneInfo("Africa/Algiers")))
open(sys.argv[1], "w", encoding="utf-8").write(page)
PY
)
rm -f "$SORTIE"
(cd "$TMP" && zip -qr "$SORTIE" veille-pharma)
echo "Paquet prêt : $SORTIE"
