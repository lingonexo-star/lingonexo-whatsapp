# Veille réglementaire pharmaceutique – Algérie (Microsoft 365)

> **Document de passation.** Résume l'étude de faisabilité faite avec Claude Code le 1er novembre 2026.
> **Statut :** étude terminée. Rien n'est encore construit dans Microsoft 365.
> **Pour reprendre :** donnez ce fichier à Claude (« lis `docs/veille-reglementaire-pharma-algerie.md` et continuons ») et répondez aux questions de la section 12.

---

## 1. Objectif

Une petite application qui tourne seule dans l'environnement Microsoft, **sans dépendre de Claude** :

- elle vérifie régulièrement (tous les jours ou le dimanche matin) les nouveaux textes réglementaires algériens ;
- elle repère ce qui concerne **l'industrie pharmaceutique** ;
- elle prévient l'équipe tout de suite (e-mail ou Teams) avec un résumé et le lien vers le texte officiel.

## 2. Conclusion : c'est faisable

Oui. Une fois en place, tout tourne dans Microsoft 365 (Power Automate, Copilot Studio ou Copilot), sans intervention de Claude.

## 3. Principe clé : partir de la source officielle, pas d'une recherche web

Demander simplement à une IA « cherche les nouveautés pharma en Algérie » donne des résultats **incomplets**. Elle peut rater un texte ou mal le résumer. Pour une veille réglementaire, ce n'est pas suffisant.

La méthode fiable consiste à partir du **Journal officiel (JORADP, joradp.dz)** :

- chaque numéro est publié en PDF avec un **numéro qui se suit** ;
- format d'adresse (édition française) : `https://www.joradp.dz/FTP/jo-francais/{année}/F{année}{numéro sur 3 chiffres}.pdf`
  (exemple : `https://www.joradp.dz/FTP/jo-francais/2026/F2026057.pdf`) ;
- édition arabe : `https://www.joradp.dz/FTP/jo-arabe/{année}/A{année}{numéro}.pdf`.

Le système vérifie donc chaque matin si **le numéro suivant existe**. S'il existe, un nouveau JO est paru, et on est sûr de ne rien rater. L'IA sert ensuite seulement à **lire, trier et résumer**.

> ⚠️ **À vérifier :** ce format d'adresse vient d'un index tiers (UpGrowth). Il n'a pas pu être testé directement, car l'environnement de Claude n'avait pas accès à joradp.dz. Il faut l'ouvrir dans un navigateur avant de construire le flux.

## 4. Les trois options Microsoft

| Option | Principe | Avantages | Limites |
|---|---|---|---|
| **1. Prompts planifiés de Copilot** | On écrit une demande dans Copilot et on la programme chaque semaine | Prêt en 5 minutes | Repose sur la recherche web, donc incomplet. Nombre d'exécutions limité. Licence Microsoft 365 Copilot obligatoire |
| **2. Power Automate + IA** ✅ *recommandé* | Un flux programmé vérifie le JO et les sites officiels, puis l'IA analyse | Fiable, traçable, entièrement automatique | Demande une licence Power Automate Premium (connecteur HTTP) |
| **3. Agent Copilot Studio** | Un agent qui se déclenche tout seul (déclencheur « Recurrence ») et envoie un rapport | Permet aussi de lui poser des questions ensuite | Facturé au message, un peu plus complexe à configurer |

L'option 1 peut servir de **test rapide**, mais pas de vrai système de veille.
L'option 3 peut venir **après**, par-dessus l'option 2, pour pouvoir interroger l'historique.

## 5. Fonctionnement recommandé (option 2 : Power Automate)

1. **Déclenchement :** tous les jours à 7h.
   En Algérie, le dimanche est un jour ouvré et le JO paraît plusieurs fois par semaine (environ 70 à 80 numéros par an). Avec une seule vérification hebdomadaire, une nouveauté pourrait être connue jusqu'à 7 jours après sa parution.
   On peut **ajouter** un récapitulatif le dimanche matin.
2. **Détection d'un nouveau JO :**
   - lire le dernier numéro traité dans la liste SharePoint de configuration (section 8) ;
   - essayer d'ouvrir le numéro suivant (n + 1) ;
   - si la réponse est **200 et que le fichier est bien un PDF**, traiter ce numéro, enregistrer n + 1, puis essayer le suivant (plusieurs JO ont pu paraître depuis la dernière vérification) ;
   - sinon (404, ou une page HTML d'erreur), s'arrêter : pas de nouveau numéro ;
   - au changement d'année, repartir à 0 avec la nouvelle année ;
   - mettre une limite à la boucle (par exemple 10 numéros par exécution).
3. **Autres sources** (section 6) : consulter les pages actualités et réglementation, puis comparer avec la dernière version enregistrée pour repérer les nouveaux éléments. Les circulaires, notes et décisions n'y paraissent pas toujours au JO.
4. **Extraction et filtrage :** extraire le texte du PDF (AI Builder, à valider lors de la construction), puis chercher les mots-clés de la section 7.
5. **Analyse par l'IA** (prompt AI Builder ou agent Copilot Studio, consigne en section 9) : type de texte, intitulé, résumé, date d'entrée en vigueur, impact, niveau d'urgence.
6. **Alerte :** e-mail Outlook ou message Teams, avec le lien vers le PDF officiel. On n'envoie rien si aucun texte n'est pertinent, sauf dans le récapitulatif du dimanche.
7. **Historique :** chaque texte détecté est enregistré dans une liste SharePoint, ce qui facilite les audits.
8. **Surveillance du flux lui-même :** si aucune vérification n'a réussi depuis 3 jours (site en panne, adresse modifiée), une alerte est envoyée. Sinon, une veille cassée peut rester silencieuse sans que personne ne s'en rende compte.

## 6. Sources à surveiller

| Source | Contenu | Priorité |
|---|---|---|
| **Journal officiel (JORADP, joradp.dz)** | Lois, ordonnances, décrets, arrêtés : la source de vérité juridique | Indispensable |
| **Ministère chargé de l'industrie pharmaceutique** | Arrêtés, circulaires, notes, communiqués | Haute |
| **ANPP** (Agence nationale des produits pharmaceutiques) | Décisions, enregistrement, nomenclature, alertes | Haute |
| **Ministère de la Santé** | Circulaires, instructions | Moyenne |
| À discuter : CNAS (remboursement), ministère du Commerce (importation) | — | À confirmer |

> Les adresses exactes des sites des ministères et de l'ANPP restent à confirmer au moment de construire le flux.

## 7. Mots-clés de filtrage (proposition)

médicament · produit pharmaceutique · produits pharmaceutiques · industrie pharmaceutique · ANPP · Agence nationale des produits pharmaceutiques · officine · pharmacien · pharmacie · dispositif médical · dispositifs médicaux · enregistrement · homologation · autorisation de mise sur le marché · nomenclature · prix · marge · remboursement · importation · fabrication · distribution en gros · stupéfiant · psychotrope · vaccin · réactif · essai clinique · pharmacovigilance · bonnes pratiques

Si on surveille aussi l'édition arabe, il faudra une liste de mots-clés en arabe. La version arabe est la version de référence, la française est une traduction.

## 8. Listes SharePoint (proposition)

**Liste « Veille – Textes détectés »**

| Colonne | Type |
|---|---|
| Titre (intitulé du texte) | Texte |
| Type de texte (loi, ordonnance, décret présidentiel, décret exécutif, arrêté, décision, circulaire) | Choix |
| Source (JO, ministère, ANPP…) | Choix |
| Numéro JO / Date JO | Texte / Date |
| Lien officiel | Lien |
| Résumé | Texte multiligne |
| Impact (élevé / moyen / faible) | Choix |
| Date d'entrée en vigueur | Date |
| Statut (Nouveau / Lu / À traiter / Clos) | Choix |
| Responsable | Personne |
| Commentaire | Texte multiligne |

**Liste « Veille – Configuration »** (clé / valeur)

- `AnneeJO` : 2026
- `DernierNumeroJO` : numéro du dernier JO traité
- `DerniereVerificationReussie` : date et heure

## 9. Consigne pour l'IA (brouillon)

```
Tu es assistant de veille réglementaire pour un établissement pharmaceutique en Algérie.
Voici le texte d'un numéro du Journal officiel algérien.

1. Repère uniquement les textes qui concernent : le médicament, les produits
   pharmaceutiques, les dispositifs médicaux, les officines, la production,
   l'importation ou la distribution pharmaceutique, les prix et le remboursement.
2. Pour chaque texte retenu, donne :
   - type (loi, ordonnance, décret présidentiel, décret exécutif, arrêté, décision)
   - numéro et date du texte
   - intitulé exact
   - résumé en 3 phrases maximum
   - date d'entrée en vigueur si elle est indiquée
   - acteurs concernés (fabricants, importateurs, distributeurs, officines…)
   - impact : élevé, moyen ou faible
   - page du Journal officiel
3. Si aucun texte ne concerne le secteur, réponds exactement : AUCUN_TEXTE_PERTINENT
4. N'invente rien. Ne cite que ce qui figure dans le texte fourni.
```

Pour que Power Automate lise la réponse facilement, on pourra demander une sortie en JSON.

## 10. Coûts indicatifs (à vérifier selon votre contrat)

- **Power Automate Premium :** environ 15 $/utilisateur/mois (nécessaire pour le connecteur HTTP).
- **IA :** crédits AI Builder ou messages Copilot Studio. Le volume est faible (environ 70 à 80 JO par an, plus quelques pages web).
- **Microsoft 365 Copilot** (seulement pour l'option 1) : environ 30 $/utilisateur/mois.

## 11. Points de vigilance

- L'IA **trie et résume**. Elle ne remplace pas la lecture du texte par un juriste ou un pharmacien.
- Si un site change de structure, le flux peut casser : c'est le rôle de l'alerte de surveillance (section 5, étape 8).
- « Instantanément » veut dire en pratique **dans les 24 heures** qui suivent la publication, avec une vérification quotidienne.
- Le format d'adresse du JO reste **à confirmer** (section 3).

## 12. Questions ouvertes (à trancher avant de construire)

1. Quelles licences avez-vous : Microsoft 365 Copilot, Power Automate Premium, Copilot Studio ?
2. Qui doit recevoir les alertes, et par quel canal (e-mail, Teams, les deux) ?
3. Alerte quotidienne, récapitulatif du dimanche, ou les deux ?
4. Faut-il surveiller l'édition arabe du JO en plus de la française ?
5. Quelles sources en plus du JO (ministère, ANPP, Santé, CNAS, Commerce) ?

## 13. Prochaines étapes

1. Répondre aux questions de la section 12.
2. Vérifier le format d'adresse du JO dans un navigateur.
3. Rédiger le guide pas à pas Power Automate en français (écran par écran).
4. Créer les deux listes SharePoint.
5. Construire et tester le flux sur quelques numéros récents du JO.
6. Mise en service, puis ajout éventuel d'un agent Copilot Studio pour interroger l'historique.

---

## Sources consultées

- [UpGrowth – Index du Journal officiel 1962-2026 (format des liens joradp.dz)](https://www.upgrowth.dz/datasets/journal-officiel-1962-2026)
- [Microsoft Learn – Event trigger overview (Copilot Studio)](https://learn.microsoft.com/microsoft-copilot-studio/authoring-triggers-about)
- [Microsoft MCS Labs – Autonomous Account News agent (déclencheur Recurrence + e-mail)](https://microsoft.github.io/mcs-labs/labs/autonomous-account-news)
- [Microsoft Agent Academy – Automate triggers](https://microsoft.github.io/agent-academy/operative/04-automate-triggers)
- [RM531911 – Microsoft 365 Copilot : Scheduled prompts](https://mc.merill.net/message/RM531911)
- [CIAOPS – Scheduled Prompts in Microsoft 365 Copilot](https://blog.ciaops.com/2026/04/21/stop-checking-start-scheduling-how-to-use-scheduled-prompts-in-microsoft-365-copilot/)
- [Microsoft Q&A – Limites de planification des agents conversationnels](https://learn.microsoft.com/en-ca/answers/questions/5933189/scheduled-prompt-trigger-not-working-for-custom-co)
