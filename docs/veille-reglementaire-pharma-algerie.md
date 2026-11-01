# Veille réglementaire pharmaceutique – Algérie : document de passation

> **Pour reprendre ce projet avec Claude :** « lis `docs/veille-reglementaire-pharma-algerie.md`
> et `veille-pharma-dz/README.md`, et continuons ».
> **Statut (1er novembre 2026) :** logiciel et portail d'administration écrits et testés (40 tests automatiques), pas encore déployés sur Azure.

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
| Installation | **Par l'utilisateur lui-même**, sur son propre abonnement Azure, via `installer.sh` dans Azure Cloud Shell | Pas de service informatique, rien à installer sur le PC |
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
2. **Installer** : suivre « Installation par vous-même » dans `veille-pharma-dz/README.md`. Le script a été
   vérifié avec une fausse commande `az`, mais pas encore sur un vrai abonnement Azure.
3. Au 1er lancement, **confirmer les sources** : le format d'adresse des PDF du JO et le flux du
   ministère de l'Industrie pharmaceutique. Ils n'ont pas pu être testés depuis l'environnement de
   Claude, qui n'a pas accès aux sites `.dz`.
4. Trouver et activer les adresses de l'**ANPP** et du **ministère de la Santé** (`sources.yaml`).
5. Donner à Claude l'accès GitHub au dépôt `lingonexo-star/lingonexo-whatsapp` : l'envoi sur
   GitHub était refusé pendant la session.
