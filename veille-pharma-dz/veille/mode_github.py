"""Version gratuite : la veille tourne dans GitHub Actions (dépôt privé), les e-mails partent par Gmail.

- Le tableau de bord est la page d'accueil du dépôt (README.md), régénérée après chaque action.
- Les administrateurs sont les personnes invitées sur le dépôt (par leur adresse e-mail).
- Les actions (vérifier, ajouter / retirer / suspendre / réactiver un destinataire, envoyer un test)
  se lancent depuis l'onglet Actions de GitHub, avec un petit formulaire.

Lancement : `python -m veille github` (variables ACTION, EMAIL, NOM, FONCTION, BIENVENUE).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .annuaire import Annuaire, ErreurAnnuaire, normaliser_email
from .config import Parametres, charger_configuration
from .mailer import construire_expediteur
from .models import ErreurSource
from .render import rendre_message
from .runner import executer, lire_journal
from .storage import Stockage, StockageLocal
from .textutil import date_fr, date_longue_fr, pluriel

ACTIONS = {
    "Lancer une vérification": "verifier",
    "Ajouter un destinataire": "ajouter",
    "Retirer un destinataire": "retirer",
    "Suspendre un destinataire": "suspendre",
    "Réactiver un destinataire": "reactiver",
    "Envoyer un e-mail de test": "tester",
}
STATUTS = {"RAS": "✅ RAS", "NOUVEAUTES": "🔵 Nouveautés", "INCOMPLET": "⚠️ Incomplète"}


class ErreurAction(Exception):
    """Demande impossible (adresse manquante, destinataire inconnu…) : message affiché tel quel."""


def _quand(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
        return f"{date_longue_fr(d.date())} à {d:%H:%M}"
    except (TypeError, ValueError):
        return iso or ""


def _statut(entree: dict) -> str:
    if entree.get("statut") == "NOUVEAUTES":
        return f"🔵 {pluriel(entree.get('nb_nouveautes', 0), 'nouveauté')}"
    return STATUTS.get(entree.get("statut"), "⚠️ Incomplète")


def _cellule(texte) -> str:
    return str(texte or "").replace("|", "/").replace("\n", " ")


def rendre_tableau_de_bord(entrees: list[dict], destinataires: list, sources: list, url_actions: str,
                           dossier: str, maintenant: datetime) -> str:
    """Page d'accueil du dépôt : état de la veille, mode d'emploi, historique, destinataires, sources."""
    l = ["# Veille réglementaire · Industrie pharmaceutique · Algérie", "",
         f"*Page mise à jour automatiquement le {date_longue_fr(maintenant.date())} à {maintenant:%H:%M} (heure d'Alger).*", ""]

    l += ["## Dernière vérification", ""]
    if entrees:
        d = entrees[0]
        sources_ok = sum(1 for s in d.get("sources", []) if s["statut"] != "erreur")
        l += [f"- **Résultat :** **{_statut(d)}**",
              f"- **Date :** {_quand(d.get('date'))}",
              f"- **Sources vérifiées :** {sources_ok} sur {len(d.get('sources', []))}",
              "- **Prochaine :** chaque matin, entre 6h15 et 7h30 (heure d'Alger)", ""]
        if d.get("statut") == "RAS":
            l += ["> **RAS** (rien à signaler) : toutes les sources ont été vérifiées et il n'y a aucune nouveauté. "
                  "Aucun e-mail n'est envoyé ces jours-là.", ""]
    else:
        l += ["Aucune vérification pour le moment. Lancez la première depuis l'onglet **Actions** (voir ci-dessous).", ""]

    l += ["## Que faire ?", "",
          f"Toutes les actions se lancent depuis l'onglet **[Actions]({url_actions})** → **Veille réglementaire** → "
          "bouton **Run workflow** : choisissez l'action, remplissez l'adresse si besoin, puis **Run workflow**. "
          "Le résultat apparaît en une à trois minutes.", "",
          "| Je veux… | Action à choisir | À remplir |", "|---|---|---|",
          "| Vérifier tout de suite | Lancer une vérification | rien |",
          "| Ajouter une personne | Ajouter un destinataire | adresse, nom, fonction |",
          "| Ne plus envoyer à quelqu'un | Retirer un destinataire | adresse |",
          "| Arrêter temporairement | Suspendre un destinataire | adresse |",
          "| Reprendre les envois | Réactiver un destinataire | adresse |",
          "| Vérifier qu'une adresse reçoit bien | Envoyer un e-mail de test | adresse |", ""]

    recentes = []
    for x in entrees:
        for el in x.get("elements", []):
            if len(recentes) < 10:
                recentes.append((x, el))
    l += ["## Dernières nouveautés", ""]
    if recentes:
        for x, el in recentes:
            note = f" · [note complète]({dossier}/{x['rapport_md']})" if x.get("rapport_md") else ""
            jour = date_fr(datetime.fromisoformat(x["date"]).date())
            l.append(f"- **{jour}** — [{_cellule(el['titre'])}]({el['url']}) — {_cellule(el['source'])}"
                     f" — impact {_cellule(el.get('impact'))}{note}")
        l.append("")
    else:
        l += ["Aucune nouveauté signalée pour le moment.", ""]

    l += ["## Historique des vérifications", "", "| Date | Résultat | Sources | E-mail |", "|---|---|---|---|"]
    for x in entrees[:30]:
        sources_x = x.get("sources", [])
        ok = sum(1 for s in sources_x if s["statut"] != "erreur")
        email = x.get("email") or {}
        envoi = (f"envoyé à {pluriel(len(email.get('destinataires', [])), 'personne')}" if email.get("envoye")
                 else ("**échec de l'envoi**" if email.get("erreur") else "—"))
        l.append(f"| {_quand(x.get('date'))} | {_statut(x)} | {ok}/{len(sources_x)} | {envoi} |")
    if not entrees:
        l.append("| — | — | — | — |")
    l.append("")

    actifs = [d for d in destinataires if d.actif]
    l += [f"## Destinataires ({len(actifs)} actif{'s' if len(actifs) > 1 else ''})", "",
          "| Nom | Adresse e-mail | Fonction | Statut |", "|---|---|---|---|"]
    for d in sorted(destinataires, key=lambda x: (not x.actif, (x.nom or x.email).lower())):
        l.append(f"| {_cellule(d.nom) or '—'} | {_cellule(d.email)} | {_cellule(d.fonction) or '—'} | "
                 f"{'Actif' if d.actif else 'Suspendu'} |")
    l.append("")

    resultats = {s["id"]: s for s in (entrees[0].get("sources", []) if entrees else [])}
    l += ["## Sources surveillées", "", "| Source | Dernier résultat |", "|---|---|"]
    for src in sources:
        if not src.actif:
            continue
        r = resultats.get(src.id)
        etat = "en attente" if r is None else (f"⚠️ {_cellule(r['detail'])}" if r["statut"] == "erreur"
                                               else f"✅ {_cellule(r['detail'])}")
        l.append(f"| {_cellule(src.nom)} | {etat} |")
    l += ["", "---", "", "*Résumés établis automatiquement : seul le texte officiel fait foi. "
          "Mode d'emploi complet : [DOCUMENTATION.md](DOCUMENTATION.md).*", ""]
    return "\n".join(l)


def _bienvenue(p: Parametres, email: str, nom: str) -> tuple[str, str]:
    contact = p.admins[0] if p.admins else ""
    return rendre_message(
        "Bienvenue dans la veille réglementaire pharmaceutique", "Bienvenue dans la veille réglementaire",
        [f"Bonjour {nom}," if nom else "Bonjour,",
         "Vous êtes désormais destinataire de la veille réglementaire sur l'industrie pharmaceutique en Algérie.",
         "Chaque matin, le Journal officiel, les sites des ministères concernés et la presse sont vérifiés. "
         "Lorsqu'un nouveau texte concerne le secteur, vous recevez une note de synthèse avec un résumé et le lien "
         "vers le texte officiel. Les jours sans nouveauté, aucun e-mail n'est envoyé."],
        None, f"Pour toute question ou pour vous désinscrire, contactez {contact}." if contact else "",
        p.organisation)


def _test(p: Parametres, nom: str) -> tuple[str, str]:
    return rendre_message(
        "Message de test – veille réglementaire pharmaceutique", "Message de test",
        [f"Bonjour {nom}," if nom else "Bonjour,",
         "Ce message confirme que les notes de veille parviennent bien à cette adresse.",
         "Aucune action n'est nécessaire."], None, "", p.organisation)


def realiser(p: Parametres, action: str, email: str = "", nom: str = "", fonction: str = "",
             bienvenue: bool = True, par: str = "", stockage: Stockage | None = None, expediteur=None,
             lanceur=None) -> str:
    """Réalise une action et renvoie le message à afficher. Lève ErreurAction si c'est impossible."""
    stockage = stockage or StockageLocal(p.dossier_donnees)
    code = ACTIONS.get(action.strip(), action.strip())
    annuaire = Annuaire(stockage, p, lambda: datetime.now(ZoneInfo(p.fuseau)))
    email = normaliser_email(email)

    def envoyeur():
        return expediteur or construire_expediteur(None, p, stockage)

    if code == "verifier":
        entree = (lanceur or (lambda: executer(p, stockage=stockage, expediteur=expediteur,
                                               declenchement="planifie" if par == "planifie" else "manuel")))()
        resume = {"RAS": "RAS : toutes les sources ont été vérifiées, aucune nouveauté.",
                  "NOUVEAUTES": f"{pluriel(entree['nb_nouveautes'], 'nouveauté')}, note envoyée.",
                  "INCOMPLET": "Vérification incomplète : au moins une source n'a pas répondu."}[entree["statut"]]
        if entree["email"].get("erreur"):
            resume += f" Attention, l'e-mail n'est pas parti : {entree['email']['erreur']}"
        return resume
    if code not in ("ajouter", "retirer", "suspendre", "reactiver", "tester"):
        raise ErreurAction(f"Action inconnue : « {action} ».")
    if not email:
        raise ErreurAction("Indiquez l'adresse e-mail de la personne concernée.")

    try:
        if code == "ajouter":
            nouveau = annuaire.ajouter(email, nom, fonction, par)
            if bienvenue:
                envoyeur().envoyer([nouveau.email], *_bienvenue(p, nouveau.email, nouveau.nom))
                return f"{nouveau.libelle} a été ajouté(e) et a reçu un message de bienvenue."
            return f"{nouveau.libelle} a été ajouté(e)."
        cible = annuaire.trouver_par_email(email)
        if cible is None:
            raise ErreurAction(f"{email} ne figure pas dans la liste des destinataires.")
        if code == "retirer":
            annuaire.retirer(cible.id)
            return f"{cible.libelle} a été retiré(e) de la liste."
        if code == "suspendre":
            annuaire.changer_statut(cible.id, False)
            return f"{cible.libelle} est suspendu(e) : plus d'envoi jusqu'à sa réactivation."
        if code == "reactiver":
            annuaire.changer_statut(cible.id, True)
            return f"{cible.libelle} est de nouveau actif(ve)."
        envoyeur().envoyer([cible.email], *_test(p, cible.nom))
        return f"Message de test envoyé à {cible.email}."
    except ErreurAnnuaire as exc:
        raise ErreurAction(str(exc)) from exc


def principal(p: Parametres, env: dict | None = None) -> int:
    """Point d'entrée du workflow GitHub : action, tableau de bord, résumé affiché dans GitHub."""
    env = os.environ if env is None else env
    action = env.get("ACTION") or "Lancer une vérification"
    par = "planifie" if env.get("GITHUB_EVENT_NAME") == "schedule" else env.get("GITHUB_ACTOR", "")
    stockage = StockageLocal(p.dossier_donnees)
    code_retour = 0
    try:
        message = realiser(p, action, env.get("EMAIL", ""), env.get("NOM", ""), env.get("FONCTION", ""),
                           env.get("BIENVENUE", "true").lower() != "false", par, stockage)
        titre = f"✅ {action}"
    except (ErreurAction, ErreurSource) as exc:
        message, titre, code_retour = str(exc), f"❌ {action} : impossible", 1

    depot = env.get("GITHUB_REPOSITORY", "")
    url_actions = f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/{depot}/actions/workflows/veille.yml" if depot else "../../actions"
    maintenant = datetime.now(ZoneInfo(p.fuseau))
    tableau = rendre_tableau_de_bord(
        lire_journal(stockage, 60), Annuaire(stockage, p).lister(), charger_configuration(p.fichier_sources).sources,
        url_actions, Path(p.dossier_donnees).name, maintenant)
    Path(env.get("VEILLE_TABLEAU_DE_BORD", "README.md")).write_text(tableau, encoding="utf-8")

    if env.get("GITHUB_STEP_SUMMARY"):
        with open(env["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as resume:
            resume.write(f"## {titre}\n\n{message}\n")
    print(f"{titre}\n{message}")
    return code_retour

