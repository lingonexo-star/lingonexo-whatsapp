#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  Installation de la veille réglementaire sur Azure, en une commande.
#
#  À lancer dans Azure Cloud Shell (https://shell.azure.com, mode Bash) :
#
#      bash veille-pharma-dz/installer.sh adresse.de.l.administrateur@exemple.com
#
#  Rien à installer sur votre ordinateur. Relancer la même commande met le
#  logiciel à jour (les réglages et la liste des destinataires sont conservés).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ICI="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$HOME/.veille-pharma.env"
REGION="${VEILLE_REGION:-francecentral}"
GROUPE="${VEILLE_GROUPE:-veille-pharma}"

etape() { printf '\n\033[1;36m[%s] %s\033[0m\n' "$1" "$2"; }
erreur() { printf '\n\033[1;31mErreur : %s\033[0m\n' "$1" >&2; exit 1; }

# ── Réglages (conservés entre deux lancements) ──────────────────────────────
az account show -o none 2>/dev/null || erreur "vous n'êtes pas connecté à Azure. Ouvrez https://shell.azure.com puis relancez."
az config set extension.use_dynamic_install=yes_without_prompt -o none 2>/dev/null || true

SUFFIXE="" SECRET="" ADMINS_ENREGISTRES="" EXISTANT=""
# shellcheck disable=SC1090
[ -f "$CONFIG" ] && source "$CONFIG"

# Installation déjà présente (par exemple depuis une autre session Cloud Shell) : on la reprend.
if [ -z "$SUFFIXE" ]; then
  EXISTANT="$(az functionapp list -g "$GROUPE" --query "[?starts_with(name, 'veille-pharma-')].name | [0]" -o tsv 2>/dev/null || true)"
  if [ -n "$EXISTANT" ]; then
    SUFFIXE="${EXISTANT#veille-pharma-}"
    reglage() { az functionapp config appsettings list -n "$EXISTANT" -g "$GROUPE" --query "[?name=='$1'].value | [0]" -o tsv; }
    SECRET="$(reglage VEILLE_SECRET)"
    ADMINS_ENREGISTRES="$(reglage VEILLE_ADMINS)"
    echo "Installation existante retrouvée : $EXISTANT (mise à jour)."
  fi
fi

ADMINS="$(echo "${*:-$ADMINS_ENREGISTRES}" | tr ' ;' ',,' | sed 's/,,*/,/g; s/^,//; s/,$//')"
if [ -z "$ADMINS" ]; then
  read -rp "Adresse(s) e-mail des administrateurs (séparées par des virgules) : " ADMINS
fi
IFS=',' read -ra LISTE_ADMINS <<< "$ADMINS"
for adresse in "${LISTE_ADMINS[@]}"; do
  [[ "$adresse" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] || erreur "adresse e-mail invalide : « $adresse »"
done

SUFFIXE="${SUFFIXE:-$(openssl rand -hex 3)}"
SECRET="${SECRET:-$(openssl rand -hex 32)}"
APP="veille-pharma-$SUFFIXE"
STOCKAGE="veillepharma$SUFFIXE"
SERVICE_EMAIL="veille-email-$SUFFIXE"
SERVICE_COMM="veille-comm-$SUFFIXE"

cat > "$CONFIG" <<EOF
SUFFIXE=$SUFFIXE
SECRET=$SECRET
ADMINS_ENREGISTRES=$ADMINS
EOF
chmod 600 "$CONFIG"

echo "Abonnement Azure : $(az account show --query name -o tsv)"
echo "Administrateur(s) : $ADMINS"

# ── 1. Préparation de l'abonnement ──────────────────────────────────────────
etape 1/6 "Préparation de l'abonnement (1 à 3 minutes la première fois)"
for espace in Microsoft.Web Microsoft.Storage Microsoft.Communication Microsoft.Insights; do
  az provider register --namespace "$espace" --wait -o none
done
az group create -n "$GROUPE" -l "$REGION" -o none

# ── 2. Stockage (journal, rapports, liste des destinataires) ────────────────
etape 2/6 "Stockage"
az storage account create -n "$STOCKAGE" -g "$GROUPE" -l "$REGION" --sku Standard_LRS --kind StorageV2 \
  --min-tls-version TLS1_2 --allow-blob-public-access false -o none

# ── 3. Application (minuteur de 7h00 + portail web) ─────────────────────────
etape 3/6 "Application Azure Functions"
if ! az functionapp show -n "$APP" -g "$GROUPE" -o none 2>/dev/null; then
  if ! az functionapp create -n "$APP" -g "$GROUPE" --storage-account "$STOCKAGE" \
       --flexconsumption-location "$REGION" --runtime python --runtime-version 3.11 -o none; then
    echo "Plan « Flex Consumption » indisponible sur cet abonnement : utilisation du plan « Consommation »."
    az functionapp create -n "$APP" -g "$GROUPE" --storage-account "$STOCKAGE" \
      --consumption-plan-location "$REGION" --os-type Linux --runtime python --runtime-version 3.11 \
      --functions-version 4 -o none
  fi
fi
HOTE="$(az functionapp show -n "$APP" -g "$GROUPE" --query defaultHostName -o tsv)"
URL="https://$HOTE"

# ── 4. Service d'e-mail Azure (aucune messagerie d'entreprise nécessaire) ───
etape 4/6 "Service d'envoi d'e-mails (quelques minutes la première fois)"
az communication email create -n "$SERVICE_EMAIL" -g "$GROUPE" --location global --data-location Europe -o none
az communication email domain create --domain-name AzureManagedDomain --email-service-name "$SERVICE_EMAIL" \
  -g "$GROUPE" --location global --domain-management AzureManaged -o none
DOMAINE_ID="$(az communication email domain show --domain-name AzureManagedDomain --email-service-name "$SERVICE_EMAIL" \
  -g "$GROUPE" --query id -o tsv)"
DOMAINE_ENVOI="$(az communication email domain show --domain-name AzureManagedDomain --email-service-name "$SERVICE_EMAIL" \
  -g "$GROUPE" --query mailFromSenderDomain -o tsv)"
az communication create -n "$SERVICE_COMM" -g "$GROUPE" --location global --data-location Europe -o none
az communication update -n "$SERVICE_COMM" -g "$GROUPE" --linked-domains "$DOMAINE_ID" -o none
ACS_CONNEXION="$(az communication list-key -n "$SERVICE_COMM" -g "$GROUPE" --query primaryConnectionString -o tsv)"
EXPEDITEUR="DoNotReply@$DOMAINE_ENVOI"

# ── 5. Réglages de l'application ────────────────────────────────────────────
etape 5/6 "Réglages"
az functionapp config appsettings set -n "$APP" -g "$GROUPE" -o none --settings \
  "VEILLE_PLANNING=0 0 6 * * *" \
  "VEILLE_ADMINS=$ADMINS" \
  "VEILLE_SECRET=$SECRET" \
  "VEILLE_URL_PUBLIQUE=$URL" \
  "VEILLE_MODE_EMAIL=acs" \
  "ACS_CONNEXION=$ACS_CONNEXION" \
  "ACS_EXPEDITEUR=$EXPEDITEUR"

# ── 6. Mise en ligne du logiciel ────────────────────────────────────────────
etape 6/6 "Mise en ligne du logiciel (2 à 5 minutes)"
PAQUET="$(mktemp -d)/veille.zip"
(cd "$ICI" && zip -qr "$PAQUET" function_app.py host.json requirements.txt sources.yaml veille -x '*/__pycache__/*')
az functionapp deployment source config-zip -n "$APP" -g "$GROUPE" --src "$PAQUET" --build-remote true -o none

cat <<EOF

────────────────────────────────────────────────────────────────────
  Installation terminée.

  Adresse du portail : $URL
  Administrateur(s)  : $ADMINS
  Expéditeur des e-mails : $EXPEDITEUR

  Envoyez l'adresse du portail à l'administrateur : il s'y connecte
  avec son adresse e-mail (il reçoit un lien de connexion).
  Pensez à vérifier les courriers indésirables lors du premier envoi.

  Mettre à jour plus tard : relancez la même commande.
  Tout supprimer :          az group delete -n $GROUPE
────────────────────────────────────────────────────────────────────
EOF
