# Veille réglementaire pharmaceutique – Algérie : document de passation

> **Pour reprendre ce projet avec Claude :** « lis `docs/veille-reglementaire-pharma-algerie.md`
> et `veille-pharma-dz/README.md`, et continuons ».
> **Statut (1er novembre 2026) :** **en service** dans le dépôt privé `lingonexo-star/veille-pharma` (GitHub Actions + Gmail
> `veille.pharma.yvm@gmail.com`), 74 tests automatiques. Première vérification faite le 1er novembre : JO n° 75/2026 trouvé,
> presse lue ; les sites des ministères bloquent les serveurs étrangers et sont suivis via Google Actualités.

## 1. Besoin exprimé

- Un **logiciel de veille** (*regulatory intelligence*) sur la réglementation de l'industrie
  pharmaceutique en Algérie.
- Il tourne **tous les matins**, **seul**, **dans le cloud**, sans intervention de Claude et sans
  machine physique.
- Il doit être **compatible avec l'environnement Microsoft**, mais **pas lancé par Copilot**.
- Sources : Journal officiel, décrets présidentiels et exécutifs, arrêtés ministériels, ministère de
  l'Industrie, ministères du Commerce (intérieur et extérieur), et plus largement tout ce qui touche à
  l'industrie pharmaceutique.
- **S'il y a du nouveau** : un e-mail est envoyé, sous forme d'article simple et propre, avec résumés,
  sources et liens.
- **S'il n'y a rien** : pas d'e-mail, mais l'utilisateur peut aller vérifier et lire **RAS**.

## 2. Décisions prises

| Sujet | Décision | Pourquoi |
|---|---|---|
| Hébergement | **Azure Functions** (cloud Microsoft), déclenchement par minuteur | Tourne seul chaque matin, sans PC ni Copilot ; quasi gratuit |
| Hébergement retenu | **Version gratuite : GitHub Actions (dépôt privé) + Gmail** — voir `veille-pharma-dz/GUIDE-GRATUIT.md` | L'utilisateur ne veut rien payer ni donner de carte bancaire |
| Installation | **Par l'utilisateur lui-même**, depuis le navigateur ; l'administrateur est invité par e-mail sur le dépôt | Pas de service informatique, rien à installer sur le PC |
| Administration (Amine) | **Par e-mail**, prêt à l'emploi : aucune installation ni compte ; l'installateur gère GitHub | Demande de l'utilisateur |
| Sources | L'administrateur peut **ajouter / retirer des sites** (testés avant enregistrement) | Demande de l'utilisateur |
| Version Azure | Conservée en option (`installer.sh`, portail web) | Si un jour un abonnement Azure est disponible |
| E-mail | **Service d'e-mail Azure** (Azure Communication Services) ; Microsoft Graph et SMTP restent possibles | Ne dépend d'aucune messagerie d'entreprise |
| Résumés | **Azure OpenAI** (service Microsoft), facultatif | Article lisible. Sans lui, l'article 1er officiel est repris |
| Preuve « RAS » | **Page Journal du portail** + historique | Chaque destinataire peut vérifier que la veille a tourné |
| Source principale | **Journal officiel** : détection du numéro suivant et lecture du PDF entier | Exhaustif. Une recherche web seule rate des textes |
| Copilot / Power Automate | **Écartés** | À la demande de l'utilisateur |
| Administration | **Portail web** hébergé dans la même Function App | L'administrateur gère lui-même les destinataires |
| Connexion | **Lien à usage unique par e-mail**, session de 12 heures | Pas de mot de passe à gérer, fonctionne avec toute adresse |
| Rôles | **Administrateur** (paramètre `VEILLE_ADMINS`) et **destinataires** (journal seulement) | Demande de l'utilisateur |

## 3. Où est le code

Dossier **`veille-pharma-dz/`** (voir son `README.md` : fonctionnement, installation pas à pas,
paramètres, coûts, limites).

## 4. Reste à faire

1. **Administrateurs** : deux adresses fournies par l'utilisateur (la sienne et celle d'Amine), à passer à
   `installer.sh`. Elles ne sont volontairement pas écrites dans le code. Les destinataires sont ensuite
   ajoutés depuis le portail.
2. **Installer la version gratuite** : suivre `veille-pharma-dz/GUIDE-GRATUIT.md` (paquet à déposer sur GitHub :
   `veille-pharma-dz/preparer-paquet-github.sh` ; avec `PAQUET_ADMINS` et `PAQUET_GMAIL`, ces valeurs sont écrites dans les workflows et seul le mot de passe Gmail reste à saisir). Vérifié par une simulation locale (git + workflow), pas encore sur GitHub.
3. **Sources confirmées le 1er novembre** : le format d'adresse des PDF du JO fonctionne (n° 75/2026 trouvé). Les sites
   miph.gov.dz, commerce.gov.dz et industrie.gov.dz ne répondent pas depuis GitHub (ConnectTimeout) : ils sont
   désactivés et remplacés par deux recherches Google Actualités (`miph_annonces`, `commerce_industrie_annonces`).
   Vérifier après quelques jours qu'elles remontent bien des annonces.
4. Trouver et activer les adresses de l'**ANPP** et du **ministère de la Santé** (`sources.yaml`).
5. Alertes techniques : envoyées seulement à l'installateur (valeur par défaut écrite dans les workflows du dépôt
   veille-pharma), pas à Amine.
