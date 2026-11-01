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
# Facultatif (dépôt privé uniquement) : valeurs par défaut écrites dans les workflows, pour n'avoir
# plus qu'un secret à créer (le mot de passe Gmail). Les réglages GitHub, s'ils existent, restent prioritaires.
if [ -n "${PAQUET_ADMINS:-}" ]; then
  sed -i "s/\${{ vars.VEILLE_ADMINS }}/\${{ vars.VEILLE_ADMINS || '$PAQUET_ADMINS' }}/" "$DOSSIER"/.github/workflows/*.yml
fi
if [ -n "${PAQUET_ALERTE:-}" ]; then
  sed -i "s/\${{ vars.VEILLE_ALERTE_ADMIN }}/\${{ vars.VEILLE_ALERTE_ADMIN || '$PAQUET_ALERTE' }}/" "$DOSSIER"/.github/workflows/*.yml
fi
if [ -n "${PAQUET_GMAIL:-}" ]; then
  sed -i "s/\${{ secrets.GMAIL_ADRESSE }}/\${{ secrets.GMAIL_ADRESSE || '$PAQUET_GMAIL' }}/" "$DOSSIER"/.github/workflows/*.yml
fi
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
