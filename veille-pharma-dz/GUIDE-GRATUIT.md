# Veille réglementaire – version gratuite (GitHub + Gmail)

**Gratuit, sans carte bancaire, rien à installer sur l'ordinateur.**

- **GitHub** (dépôt privé) fait tourner la veille chaque matin dans son cloud, garde l'historique
  et affiche le tableau de bord.
- **Gmail** envoie les notes de veille.
- Les **administrateurs** (par exemple Amine) n'ont **rien à installer et aucun compte à créer** : ils administrent
  la veille **par simple e-mail**, en écrivant à l'adresse de la veille (voir « Administration par e-mail »).

Le logiciel est le même que la version Azure. Seuls l'hébergement et l'envoi des e-mails changent.

---

## Installation (environ 20 minutes, une seule fois)

### A. Gmail : l'adresse de la veille (5 minutes)

0. **Créez une adresse Gmail dédiée à la veille** (par exemple `veille.pharma.yvm@gmail.com`), gratuite. C'est elle qui
   envoie les notes et qui reçoit les commandes des administrateurs : ne prenez pas une boîte personnelle.
1. Ouvrez https://myaccount.google.com/security et activez la **Validation en deux étapes**
   si ce n'est pas déjà fait.
2. Ouvrez https://myaccount.google.com/apppasswords, tapez le nom `Veille`, puis cliquez sur **Créer**.
3. **Notez les 16 lettres** affichées : c'est le mot de passe qui servira à envoyer les e-mails.
   Il ne donne pas accès à votre compte Google lui-même.

### B. GitHub : créer le dépôt (10 minutes)

4. Connectez-vous sur https://github.com (ou créez un compte gratuit).
5. En haut à droite, cliquez sur **+**, puis **New repository**. Nom : `veille-pharma`.
   Cochez **Private**, puis cliquez sur **Create repository**.
6. Sur la page du dépôt, cliquez sur le lien **uploading an existing file**. Décompressez
   `veille-pharma-github.zip` sur votre ordinateur, ouvrez le dossier obtenu, sélectionnez **tout son
   contenu** (y compris le dossier `.github`) et glissez-le dans la page. Cliquez sur **Commit changes**.
   > Si le dossier `.github` n'apparaît pas dans la liste envoyée : **Add file** → **Create new file**,
   > nommez-le `.github/workflows/veille.yml`, collez le contenu du fichier du même nom, puis cliquez sur
   > **Commit changes**.

### C. GitHub : les réglages (5 minutes)

7. **Settings** → **Secrets and variables** → **Actions**.
   - Onglet **Secrets** → **New repository secret**, deux fois :
     - `GMAIL_ADRESSE` : votre adresse Gmail
     - `GMAIL_MOT_DE_PASSE_APPLICATION` : les 16 lettres de l'étape 3
   - Onglet **Variables** → **New repository variable** :
     - `VEILLE_ADMINS` : les adresses des administrateurs, séparées par des virgules. La première est
       indiquée comme contact en bas des e-mails.
8. Onglet **Actions**. Si GitHub le demande, autorisez les workflows. Cliquez ensuite sur
   **Veille réglementaire** → **Run workflow** → laissez « Lancer une vérification » → **Run workflow**.
   Deux minutes plus tard, la page d'accueil du dépôt affiche le **tableau de bord**. La première
   vérification sert de point de départ et indique **RAS**.
9. Envoyez à l'administrateur le **guide PDF** et l'adresse de la veille. Pour vérifier que tout marche, il écrit à
   cette adresse un message avec l'objet « Aide » : la veille lui répond avec le mode d'emploi.
   *(Facultatif : vous pouvez aussi l'inviter sur le dépôt GitHub, Settings → Collaborators, s'il veut voir le
   tableau de bord détaillé.)*

C'est terminé : la veille tourne seule chaque matin, vers 6h15-7h30 (heure d'Alger).

---

## Administration par e-mail (pour l'administrateur)

L'administrateur écrit à l'adresse de la veille, **depuis son adresse** (celle indiquée dans `VEILLE_ADMINS`).
L'objet du message indique la commande, le contenu indique les personnes ou les sites (une ligne chacun).
La veille répond en moins de 30 minutes, du dimanche au jeudi entre 7h et 19h (heure d'Alger).

| Objet du message | Dans le message | Ce que fait la veille |
|---|---|---|
| Ajouter | `adresse, nom, fonction` (une ligne par personne) | inscrit la personne et lui envoie un message de bienvenue |
| Retirer · Suspendre · Réactiver · Test | une adresse par ligne | retire, met en pause, reprend, envoie un e-mail de test |
| Source | `adresse du site, nom` | teste le site puis le surveille chaque matin |
| Retirer source | adresse du site | ne le surveille plus |
| État | rien | renvoie le tableau de bord : RAS ou nouveautés, état des sources |
| Vérifier | rien | lance une vérification tout de suite |
| Liste · Aide | rien | renvoie les destinataires et les sources, ou le mode d'emploi |

Sécurité : seuls les messages des administrateurs, authentifiés par leur messagerie (DMARC/DKIM/SPF), sont pris en
compte. Les autres messages de la boîte ne sont ni lus ni modifiés.

## Au quotidien (pour vous, sur GitHub)

| Je veux… | Que faire |
|---|---|
| Savoir si la veille a tourné | Ouvrir la page d'accueil du dépôt : « RAS » ou les nouveautés du jour |
| Lire une note de veille | Dans l'e-mail reçu, ou « note complète » sur le tableau de bord |
| Ajouter une personne | **Actions** → **Veille réglementaire** → **Run workflow** → « Ajouter un destinataire » + adresse, nom, fonction |
| Retirer, suspendre, réactiver | Même chemin, en choisissant l'action correspondante et en indiquant l'adresse |
| Vérifier qu'une adresse reçoit bien | Même chemin → « Envoyer un e-mail de test » |
| Vérifier tout de suite | Même chemin → « Lancer une vérification » |
| Surveiller un nouveau site | Même chemin → « Ajouter une source » + nom et adresse de la page (actualités, textes réglementaires ou flux RSS). L'adresse est testée avant d'être enregistrée |
| Ne plus surveiller un site ajouté | Même chemin → « Retirer une source » + adresse (ou nom) du site |

Après chaque action, GitHub affiche le résultat dans la page de l'exécution : ✅ si l'action a réussi,
❌ avec l'explication sinon.

## Bon à savoir

- **Coût :** zéro. Une vérification prend environ 2 minutes, et le forfait gratuit de GitHub en
  offre 2 000 par mois pour un dépôt privé.
- **Confidentialité :** le dépôt est privé. Seules les personnes invitées voient le tableau de bord et
  la liste des destinataires. Chaque destinataire reçoit son propre e-mail et ne voit pas les autres
  adresses.
- **E-mails :** ils partent de l'adresse Gmail configurée. Au premier envoi, vérifiez les courriers
  indésirables.
- **Limite Gmail :** 500 e-mails par jour, largement suffisant.
- **Résumés par IA (facultatif) :** sans IA, la note reprend l'article 1er de chaque texte officiel.
  Pour des résumés rédigés, ajoutez les variables `IA_URL` et `IA_MODELE` et le secret `IA_CLE` d'un
  service compatible OpenAI. Certains, comme l'offre gratuite de Google AI Studio, ne demandent pas de
  carte bancaire.
- **Si « Incomplète » s'affiche plusieurs jours de suite :** un site officiel a probablement changé
  d'adresse. Il faut corriger `sources.yaml`.
