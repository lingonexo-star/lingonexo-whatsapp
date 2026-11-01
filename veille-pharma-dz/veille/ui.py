"""Pages HTML du portail : connexion, tableau de bord, destinataires, journal, sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape

from .textutil import date_fr, date_longue_fr, pluriel

PRODUIT = "Veille réglementaire"
SOUS_TITRE = "Industrie pharmaceutique · Algérie"


def e(texte) -> str:
    return escape(str(texte or ""), quote=True)


@dataclass
class Contexte:
    email: str
    role: str  # admin | lecteur
    jeton: str  # jeton anti-falsification des formulaires
    organisation: str = ""


MESSAGES = {
    "deconnecte": ("info", "Vous êtes déconnecté."),
    "ajoute": ("ok", "Destinataire ajouté. Il recevra le prochain rapport."),
    "ajoute_bienvenue": ("ok", "Destinataire ajouté et message de bienvenue envoyé."),
    "ajoute_sans_bienvenue": ("alerte", "Destinataire ajouté, mais le message de bienvenue n'a pas pu être envoyé."),
    "suspendu": ("info", "Destinataire suspendu : il ne recevra plus le rapport jusqu'à sa réactivation."),
    "reactive": ("ok", "Destinataire réactivé."),
    "retire": ("info", "Destinataire retiré de la liste."),
    "test_envoye": ("ok", "Message de test envoyé."),
    "test_echec": ("erreur", "Le message de test n'a pas pu être envoyé. Vérifiez la configuration de la messagerie."),
    "verification": ("ok", "Vérification terminée. Le résultat figure ci-dessous."),
    "verification_echec": ("erreur", "La vérification n'a pas pu aboutir. Consultez le journal pour le détail."),
    "introuvable": ("erreur", "Ce destinataire n'existe plus."),
    "session": ("erreur", "Le formulaire a expiré. Recommencez l'opération."),
}

STATUTS = {
    "RAS": ("RAS", "ok", "Toutes les sources ont été vérifiées. Aucune nouveauté."),
    "NOUVEAUTES": ("Nouveautés", "info", "Des nouveautés ont été envoyées aux destinataires."),
    "INCOMPLET": ("Incomplète", "alerte", "Au moins une source n'a pas pu être vérifiée."),
}

CSS = """
:root{
  --fond:#f3f5f7;--surface:#ffffff;--surface-2:#f7f9fa;--texte:#17242c;--doux:#5b6b75;--bord:#dde3e7;
  --accent:#0b4f6c;--accent-survol:#093f57;--accent-doux:#e3eef3;--sur-accent:#ffffff;
  --barre:#0b3a50;--barre-texte:#e6f0f4;--barre-doux:#9fbfcd;
  --ok:#067647;--ok-f:#e6f5ec;--info:#1d5fbf;--info-f:#e8f0fc;--alerte:#a1470a;--alerte-f:#fdf2e3;
  --erreur:#b42318;--erreur-f:#fdeceb;--neutre:#56636c;--neutre-f:#eef1f3;
  --police:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  --mono:"Cascadia Mono",Consolas,"SFMono-Regular",Menlo,monospace;
  color-scheme:light}
@media (prefers-color-scheme:dark){:root{
  --fond:#0d151a;--surface:#141f26;--surface-2:#17242c;--texte:#e3ebef;--doux:#9cafba;--bord:#26353e;
  --accent:#6cc3e8;--accent-survol:#8fd2ef;--accent-doux:#12303d;--sur-accent:#0b1a21;
  --barre:#08202c;--barre-texte:#e3ebef;--barre-doux:#86a8b7;
  --ok:#5ad08a;--ok-f:#10291c;--info:#86b5ff;--info-f:#14233d;--alerte:#f2b052;--alerte-f:#2d210c;
  --erreur:#ff8a80;--erreur-f:#3a1715;--neutre:#a3b0b8;--neutre-f:#1d2a32;color-scheme:dark}}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--fond);color:var(--texte);font:15px/1.55 var(--police);-webkit-font-smoothing:antialiased}
a{color:var(--accent)}
.enveloppe{max-width:1180px;margin:0 auto;padding-left:max(20px,env(safe-area-inset-left,0px));padding-right:max(20px,env(safe-area-inset-right,0px))}
/* Barre supérieure */
.barre{background:var(--barre);color:var(--barre-texte)}
.barre .enveloppe{display:flex;align-items:center;gap:24px;min-height:60px;padding-block:8px}
.marque{display:flex;align-items:center;gap:12px;color:inherit;text-decoration:none;flex:none}
.marque .monogramme{width:34px;height:34px;border-radius:6px;background:#1b7a9f;color:#fff;display:grid;place-items:center;
  font-weight:700;font-size:13px;letter-spacing:.04em;line-height:1}
.marque .nom strong{display:block;font-size:15px;font-weight:600;line-height:1.25}
.marque .nom span{display:block;font-size:12px;color:var(--barre-doux);line-height:1.25}
nav.principale{display:flex;gap:4px;flex-wrap:wrap}
nav.principale a{color:var(--barre-doux);text-decoration:none;font-size:14px;font-weight:500;padding:8px 12px;border-radius:6px}
nav.principale a:hover{color:var(--barre-texte);background:rgba(255,255,255,.06)}
nav.principale a.actif{color:var(--barre-texte);background:rgba(255,255,255,.1)}
.compte{margin-left:auto;display:flex;align-items:center;gap:10px;font-size:13px;color:var(--barre-doux);min-width:0}
.compte .adresse{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:240px}
@media (max-width:1000px){.barre .enveloppe{flex-wrap:wrap;row-gap:4px}.compte{margin-left:0;width:100%;padding-bottom:6px}
  nav.principale{order:3;width:100%}}
.compte .role{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--barre-texte);
  border:1px solid rgba(255,255,255,.25);border-radius:4px;padding:1px 6px}
.compte button{background:transparent;color:var(--barre-texte);border:1px solid rgba(255,255,255,.3);border-radius:6px;
  font:500 13px var(--police);padding:6px 10px;cursor:pointer}
.compte button:hover{background:rgba(255,255,255,.08)}
/* Contenu */
main{padding-block:28px 56px;display:flex;flex-direction:column;gap:20px}
.entete-page{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
.entete-page h1{font-size:24px;font-weight:600;margin:0;line-height:1.25}
.entete-page p{margin:4px 0 0;color:var(--doux);max-width:70ch}
.carte{background:var(--surface);border:1px solid var(--bord);border-radius:8px}
.carte>.titre{display:flex;align-items:center;justify-content:space-between;gap:4px 12px;flex-wrap:wrap;padding:14px 18px;border-bottom:1px solid var(--bord)}
.carte>.titre h2{font-size:15px;font-weight:600;margin:0}
.carte>.titre span{font-size:13px;color:var(--doux)}
.carte>.corps{padding:16px 18px}
.grille-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px;align-items:start}
.indicateurs{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px}
.indicateur{background:var(--surface);border:1px solid var(--bord);border-radius:8px;padding:16px 18px;display:flex;flex-direction:column;gap:6px;min-width:0}
.indicateur .libelle{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--doux);font-weight:600}
.indicateur .valeur{font-size:28px;font-weight:600;line-height:1.15;font-variant-numeric:tabular-nums}
.indicateur .precision{font-size:13px;color:var(--doux)}
.badge{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:2px 8px;border-radius:4px;white-space:nowrap}
.badge::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.ok{color:var(--ok);background:var(--ok-f)}.info{color:var(--info);background:var(--info-f)}
.alerte{color:var(--alerte);background:var(--alerte-f)}.erreur{color:var(--erreur);background:var(--erreur-f)}
.neutre{color:var(--neutre);background:var(--neutre-f)}
.valeur.ok,.valeur.info,.valeur.alerte{background:none}
.bandeau{padding:12px 16px;border-radius:6px;font-size:14px;border:1px solid transparent}
.bandeau.ok{border-color:color-mix(in srgb,var(--ok) 25%,transparent)}
.bandeau.info{border-color:color-mix(in srgb,var(--info) 25%,transparent)}
.bandeau.alerte{border-color:color-mix(in srgb,var(--alerte) 25%,transparent)}
.bandeau.erreur{border-color:color-mix(in srgb,var(--erreur) 25%,transparent)}
/* Listes */
.liste{list-style:none;margin:0;padding:0}
.liste li{display:flex;gap:12px;align-items:flex-start;padding:11px 18px;border-top:1px solid var(--bord)}
.liste li:first-child{border-top:0}
.liste .principal{flex:1;min-width:0}
.liste .principal a{font-weight:600;text-decoration:none}
.liste .principal a:hover{text-decoration:underline}
.liste .secondaire{font-size:13px;color:var(--doux)}
.vide{padding:22px 18px;color:var(--doux);font-size:14px}
/* Tableaux */
.defilement{overflow-x:auto}
table.donnees{width:100%;border-collapse:collapse;font-size:14px}
table.donnees th{text-align:left;font-size:12px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--doux);
  padding:10px 14px;background:var(--surface-2);border-bottom:1px solid var(--bord);white-space:nowrap}
table.donnees td{padding:12px 14px;border-bottom:1px solid var(--bord);vertical-align:middle}
table.donnees tr:last-child td{border-bottom:0}
table.donnees tr.suspendu td{color:var(--doux)}
.cellule-nom strong{display:block;font-weight:600}
.cellule-nom span{font-size:13px;color:var(--doux)}
.mono{font-family:var(--mono);font-size:13px}
.actions{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.actions form{margin:0}
@media (max-width:720px){
  table.empile thead{display:none}
  table.empile,table.empile tbody,table.empile tr,table.empile td{display:block;width:100%}
  table.empile tr{padding:12px 16px;border-bottom:1px solid var(--bord)}
  table.empile tr:last-child{border-bottom:0}
  table.empile td{border:0;padding:3px 0;min-width:0!important}
  table.empile td[data-libelle]::before{content:attr(data-libelle);display:block;font-size:11px;letter-spacing:.05em;
    text-transform:uppercase;color:var(--doux);font-weight:600;margin-top:6px}
  table.empile .actions{justify-content:flex-start;margin-top:8px}
  table.empile .mono{word-break:break-all}}
.etiquette{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--accent);border:1px solid var(--accent-doux);
  background:var(--accent-doux);border-radius:4px;padding:1px 6px;margin-left:6px;font-weight:600}
/* Boutons et champs */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font:600 14px var(--police);padding:9px 16px;
  border-radius:6px;border:1px solid var(--accent);background:var(--accent);color:var(--sur-accent);cursor:pointer;text-decoration:none}
.btn:hover{background:var(--accent-survol);border-color:var(--accent-survol)}
.btn.secondaire{background:var(--surface);color:var(--texte);border-color:var(--bord)}
.btn.secondaire:hover{background:var(--surface-2)}
.btn.petit{font-size:13px;padding:5px 10px}
.btn.danger{background:var(--surface);color:var(--erreur);border-color:var(--bord)}
.btn.danger:hover{background:var(--erreur-f)}
.btn:disabled{opacity:.6;cursor:progress}
.btn:focus-visible,input:focus-visible,nav a:focus-visible,.compte button:focus-visible{outline:3px solid color-mix(in srgb,var(--accent) 40%,transparent);outline-offset:2px}
form.ajout{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px 16px;align-items:end}
.champ{display:flex;flex-direction:column;gap:6px;min-width:0}
.champ label{font-size:13px;font-weight:600}
.champ input{font:15px var(--police);padding:9px 11px;border:1px solid var(--bord);border-radius:6px;background:var(--surface);color:var(--texte);width:100%}
.champ .aide{font-size:12px;color:var(--doux)}
.case{display:flex;gap:8px;align-items:center;font-size:14px;grid-column:1/-1}
.pied-form{grid-column:1/-1;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
/* Journal */
details.execution{border-top:1px solid var(--bord)}
details.execution:first-of-type{border-top:0}
details.execution summary{cursor:pointer;list-style:none;display:grid;grid-template-columns:minmax(210px,1.2fr) auto 1fr;gap:12px;align-items:center;padding:12px 18px}
details.execution summary::-webkit-details-marker{display:none}
details.execution summary .quand{font-weight:600}
details.execution summary .info-ligne{color:var(--doux);font-size:13px;text-align:right}
details.execution[open] summary{background:var(--surface-2)}
.detail{padding:6px 18px 16px;font-size:14px;display:flex;flex-direction:column;gap:10px}
.detail h3{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--doux);margin:6px 0 0}
.detail ul{margin:0;padding-left:18px}
.detail li{margin:3px 0}
@media (max-width:640px){details.execution summary{grid-template-columns:1fr auto}details.execution summary .info-ligne{grid-column:1/-1;text-align:left}}
/* Connexion */
.connexion{min-height:100vh;display:grid;place-items:center;padding:32px max(20px,env(safe-area-inset-left,0px))}
.connexion .boite{width:100%;max-width:420px;display:flex;flex-direction:column;gap:18px}
.connexion .marque{color:var(--texte)}
.connexion .marque .nom span{color:var(--doux)}
.connexion .carte .corps{padding:26px;display:flex;flex-direction:column;gap:16px}
.connexion h1{font-size:20px;margin:0}
.connexion p{margin:0;color:var(--doux);font-size:14px}
.connexion .btn{width:100%;padding:11px 16px}
.connexion .mentions{font-size:12px;color:var(--doux);text-align:center}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def _document(titre: str, corps: str) -> str:
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow"><title>{e(titre)} · {PRODUIT}</title><style>{CSS}</style></head>
<body>{corps}
<script>
document.querySelectorAll('form[data-attente]').forEach(function(f){{f.addEventListener('submit',function(){{
  var b=f.querySelector('button[type=submit]');if(b){{b.disabled=true;b.textContent=f.dataset.attente;}}}});}});
document.querySelectorAll('form[data-confirmer]').forEach(function(f){{f.addEventListener('submit',function(ev){{
  if(!window.confirm(f.dataset.confirmer)){{ev.preventDefault();}}}});}});
</script></body></html>"""


def _marque(organisation: str = "") -> str:
    return (f'<a class="marque" href="/"><span class="monogramme" aria-hidden="true">VR</span>'
            f'<span class="nom"><strong>{PRODUIT}</strong><span>{e(organisation or SOUS_TITRE)}</span></span></a>')


def _champ_jeton(ctx: Contexte) -> str:
    return f'<input type="hidden" name="jeton" value="{e(ctx.jeton)}">'


def page(titre: str, contenu: str, ctx: Contexte, actif: str, flash: str | None = None) -> str:
    liens = [("tableau-de-bord", "Tableau de bord"), ("destinataires", "Destinataires"),
             ("journal", "Journal"), ("sources", "Sources")] if ctx.role == "admin" else [("journal", "Journal")]
    courant = ' class="actif" aria-current="page"'
    nav = "".join(f'<a href="/{c}"{courant if c == actif else ""}>{l}</a>' for c, l in liens)
    message = ""
    if flash in MESSAGES:
        genre, texte = MESSAGES[flash]
        message = f'<div class="bandeau {genre}" role="status">{e(texte)}</div>'
    role = "Administrateur" if ctx.role == "admin" else "Destinataire"
    corps = f"""<header class="barre"><div class="enveloppe">
{_marque(ctx.organisation)}
<nav class="principale" aria-label="Navigation principale">{nav}</nav>
<div class="compte"><span class="adresse" title="{e(ctx.email)}">{e(ctx.email)}</span><span class="role">{role}</span>
<form method="post" action="/deconnexion">{_champ_jeton(ctx)}<button type="submit">Déconnexion</button></form></div>
</div></header>
<main class="enveloppe">{message}{contenu}</main>"""
    return _document(titre, corps)


def _entete(titre: str, description: str = "", actions: str = "") -> str:
    return (f'<div class="entete-page"><div><h1>{e(titre)}</h1>'
            f'{f"<p>{e(description)}</p>" if description else ""}</div>{actions}</div>')


def _quand(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
        return f"{date_longue_fr(d.date()).capitalize()} à {d:%H:%M}"
    except (TypeError, ValueError):
        return iso or ""


def _badge_statut(entree: dict) -> str:
    libelle, genre, _ = STATUTS.get(entree.get("statut"), STATUTS["INCOMPLET"])
    if entree.get("statut") == "NOUVEAUTES":
        libelle = pluriel(entree.get("nb_nouveautes", 0), "nouveauté")
    return f'<span class="badge {genre}">{e(libelle)}</span>'


# ---------------------------------------------------------------------------------------
#  Connexion
# ---------------------------------------------------------------------------------------
def _page_connexion(titre: str, contenu: str, organisation: str) -> str:
    corps = f"""<div class="connexion"><div class="boite">
{_marque(organisation)}
<div class="carte"><div class="corps">{contenu}</div></div>
<div class="mentions">Accès réservé à l'administrateur et aux destinataires de la veille.</div>
</div></div>"""
    return _document(titre, corps)


def page_connexion(organisation: str = "", erreur: str = "", info: str = "", email: str = "") -> str:
    bandeau = ""
    if erreur:
        bandeau = f'<div class="bandeau erreur" role="alert">{e(erreur)}</div>'
    elif info:
        bandeau = f'<div class="bandeau info" role="status">{e(info)}</div>'
    contenu = f"""<div><h1>Connexion au portail</h1></div>
<p>Saisissez votre adresse e-mail professionnelle. Vous recevrez un lien de connexion personnel, valable 15 minutes.</p>
{bandeau}
<form method="post" action="/connexion" data-attente="Envoi en cours…" style="display:flex;flex-direction:column;gap:14px">
<div class="champ"><label for="email">Adresse e-mail</label>
<input id="email" name="email" type="email" autocomplete="email" required value="{e(email)}" placeholder="prenom.nom@entreprise.dz"></div>
<button class="btn" type="submit">Recevoir le lien de connexion</button></form>"""
    return _page_connexion("Connexion", contenu, organisation)


def page_lien_envoye(organisation: str = "") -> str:
    contenu = """<div><h1>Vérifiez votre messagerie</h1></div>
<p>Si cette adresse a accès au portail, un e-mail contenant votre lien de connexion vient de lui être envoyé.
Le lien est valable 15 minutes et ne fonctionne qu'une seule fois.</p>
<p>Pensez à regarder dans les courriers indésirables.</p>
<a class="btn secondaire" href="/connexion">Utiliser une autre adresse</a>"""
    return _page_connexion("Vérifiez votre messagerie", contenu, organisation)


def page_confirmer(jeton: str, valide: bool, organisation: str = "") -> str:
    if not valide:
        contenu = """<div><h1>Lien expiré</h1></div>
<p>Ce lien de connexion n'est plus valide : il a expiré ou a déjà été utilisé.</p>
<a class="btn" href="/connexion">Demander un nouveau lien</a>"""
    else:
        contenu = f"""<div><h1>Ouvrir votre session</h1></div>
<p>Confirmez pour accéder au portail de veille. Votre session restera ouverte 12 heures sur cet appareil.</p>
<form method="post" action="/connexion/confirmer"><input type="hidden" name="lien" value="{e(jeton)}">
<button class="btn" type="submit">Ouvrir ma session</button></form>"""
    return _page_connexion("Connexion", contenu, organisation)


def page_erreur(titre: str, message: str, ctx: Contexte | None = None) -> str:
    contenu = (f'{_entete(titre, message)}<div><a class="btn secondaire" href="/">Retour à l\'accueil</a></div>')
    if ctx:
        return page(titre, contenu, ctx, "")
    return _page_connexion(titre, f"<div><h1>{e(titre)}</h1></div><p>{e(message)}</p>"
                                  f'<a class="btn secondaire" href="/connexion">Se connecter</a>', "")


# ---------------------------------------------------------------------------------------
#  Tableau de bord
# ---------------------------------------------------------------------------------------
def page_tableau_de_bord(ctx: Contexte, flash: str | None, derniere: dict | None, prochaine: datetime | None,
                         nb_actifs: int, nb_suspendus: int, nouveautes_30j: int,
                         recentes: list[dict]) -> str:
    if derniere:
        libelle, genre, explication = STATUTS.get(derniere["statut"], STATUTS["INCOMPLET"])
        if derniere["statut"] == "NOUVEAUTES":
            libelle = pluriel(derniere.get("nb_nouveautes", 0), "nouveauté")
        tuile_derniere = (f'<span class="valeur" style="color:var(--{genre})">{e(libelle)}</span>'
                          f'<span class="precision">{e(_quand(derniere["date"]))}</span>')
    else:
        tuile_derniere = ('<span class="valeur" style="color:var(--doux)">—</span>'
                          '<span class="precision">Aucune vérification pour le moment</span>')
    tuile_prochaine = (f'<span class="valeur">{prochaine:%H:%M}</span>'
                       f'<span class="precision">{e(date_longue_fr(prochaine.date()).capitalize())} (heure d\'Alger)</span>'
                       if prochaine else '<span class="valeur">—</span><span class="precision">Selon le planning Azure</span>')
    indicateurs = f"""<div class="indicateurs">
<div class="indicateur"><span class="libelle">Dernière vérification</span>{tuile_derniere}</div>
<div class="indicateur"><span class="libelle">Prochaine vérification</span>{tuile_prochaine}</div>
<div class="indicateur"><span class="libelle">Destinataires actifs</span><span class="valeur">{nb_actifs}</span>
<span class="precision">{pluriel(nb_suspendus, "suspendu")} · <a href="/destinataires">Gérer</a></span></div>
<div class="indicateur"><span class="libelle">Nouveautés sur 30 jours</span><span class="valeur">{nouveautes_30j}</span>
<span class="precision"><a href="/journal">Voir le journal</a></span></div></div>"""

    if recentes:
        items = "".join(
            f'<li><div class="principal"><a href="{e(x["url"])}" target="_blank" rel="noopener">{e(x["titre"])}</a>'
            f'<div class="secondaire">{e(x["type"])} · {e(x["source"])} · {e(x["jour"])}</div></div>'
            f'<a class="btn secondaire petit" href="/rapports/{e(x["rapport"])}">Rapport</a></li>' for x in recentes)
        nouveautes = f'<ul class="liste">{items}</ul>'
    else:
        nouveautes = '<div class="vide">Aucune nouveauté signalée pour le moment.</div>'

    if derniere:
        sources = "".join(
            f'<li><span class="badge {"ok" if s["statut"] != "erreur" else "erreur"}">'
            f'{"Vérifiée" if s["statut"] != "erreur" else "Échec"}</span>'
            f'<div class="principal"><strong>{e(s["nom"])}</strong><div class="secondaire">{e(s["detail"])}</div></div></li>'
            for s in derniere.get("sources", []))
        etat_sources = f'<ul class="liste">{sources}</ul>'
    else:
        etat_sources = '<div class="vide">L\'état des sources apparaîtra après la première vérification.</div>'

    action = f"""<form method="post" action="/verification" data-attente="Vérification en cours…">{_champ_jeton(ctx)}
<button class="btn" type="submit">Lancer une vérification</button></form>"""
    contenu = (
        _entete("Tableau de bord", "Suivi de la veille quotidienne : chaque matin, les sources officielles sont "
                "vérifiées et les nouveautés envoyées aux destinataires.", action)
        + indicateurs
        + f"""<div class="grille-2">
<section class="carte"><div class="titre"><h2>Dernières nouveautés</h2><span>{len(recentes)} affichée(s)</span></div>{nouveautes}</section>
<section class="carte"><div class="titre"><h2>État des sources</h2><span>Dernière vérification</span></div>{etat_sources}</section>
</div>""")
    return page("Tableau de bord", contenu, ctx, "tableau-de-bord", flash)


# ---------------------------------------------------------------------------------------
#  Destinataires
# ---------------------------------------------------------------------------------------
def page_destinataires(ctx: Contexte, flash: str | None, destinataires: list, admins: list[str],
                       erreur: str = "", valeurs: dict | None = None) -> str:
    valeurs = valeurs or {}
    actifs = sum(1 for d in destinataires if d.actif)
    bandeau = f'<div class="bandeau erreur" role="alert">{e(erreur)}</div>' if erreur else ""
    bienvenue = "checked" if valeurs.get("bienvenue", "1") else ""
    formulaire = f"""<section class="carte"><div class="titre"><h2>Ajouter un destinataire</h2>
<span>La personne recevra le rapport dès la prochaine nouveauté</span></div><div class="corps">{bandeau}
<form class="ajout" method="post" action="/destinataires" style="{'margin-top:12px' if bandeau else ''}">{_champ_jeton(ctx)}
<div class="champ"><label for="nom">Nom complet</label><input id="nom" name="nom" autocomplete="off" maxlength="120" value="{e(valeurs.get('nom'))}" placeholder="Prénom Nom"></div>
<div class="champ"><label for="email">Adresse e-mail <span aria-hidden="true">*</span></label><input id="email" name="email" type="email" required maxlength="254" autocomplete="off" value="{e(valeurs.get('email'))}" placeholder="prenom.nom@entreprise.dz"></div>
<div class="champ"><label for="fonction">Fonction</label><input id="fonction" name="fonction" maxlength="120" autocomplete="off" value="{e(valeurs.get('fonction'))}" placeholder="Pharmacien responsable"></div>
<label class="case"><input type="checkbox" name="bienvenue" value="1" {bienvenue}> Envoyer un message de bienvenue expliquant le fonctionnement de la veille</label>
<div class="pied-form"><button class="btn" type="submit">Ajouter le destinataire</button></div>
</form></div></section>"""

    lignes = []
    for d in sorted(destinataires, key=lambda x: (not x.actif, (x.nom or x.email).lower())):
        statut = '<span class="badge ok">Actif</span>' if d.actif else '<span class="badge neutre">Suspendu</span>'
        admin = '<span class="etiquette">Admin</span>' if d.email in admins else ""
        bascule = ("suspendre", "Suspendre") if d.actif else ("reactiver", "Réactiver")
        try:
            ajoute = date_fr(datetime.fromisoformat(d.ajoute_le).date())
        except (TypeError, ValueError):
            ajoute = ""

        def bouton(action: str, libelle: str, classe: str = "secondaire", confirmer: str = "") -> str:
            attribut = f' data-confirmer="{e(confirmer)}"' if confirmer else ""
            return (f'<form method="post" action="/destinataires/action"{attribut}>{_champ_jeton(ctx)}'
                    f'<input type="hidden" name="id" value="{e(d.id)}"><input type="hidden" name="action" value="{action}">'
                    f'<button class="btn {classe} petit" type="submit">{libelle}</button></form>')

        actions = (bouton("tester", "Envoyer un test") if d.actif else "") + bouton(*bascule) + bouton(
            "retirer", "Retirer", "danger", f"Retirer {d.libelle} de la liste des destinataires ?")
        lignes.append(f"""<tr class="{'' if d.actif else 'suspendu'}">
<td class="cellule-nom"><strong>{e(d.nom or '—')}{admin}</strong><span>{e(d.fonction)}</span></td>
<td class="mono" data-libelle="Adresse e-mail">{e(d.email)}</td><td data-libelle="Statut">{statut}</td>
<td data-libelle="Ajouté le">{e(ajoute)}</td><td><div class="actions">{actions}</div></td></tr>""")
    tableau = (f"""<div class="defilement"><table class="donnees empile"><thead><tr><th>Nom et fonction</th><th>Adresse e-mail</th>
<th>Statut</th><th>Ajouté le</th><th style="text-align:right">Actions</th></tr></thead><tbody>{''.join(lignes)}</tbody></table></div>"""
               if lignes else '<div class="vide">Aucun destinataire. Ajoutez la première personne ci-dessus.</div>')
    liste = (f'<section class="carte"><div class="titre"><h2>Liste de diffusion</h2>'
             f'<span>{pluriel(actifs, "destinataire actif", "destinataires actifs")} sur {len(destinataires)}</span></div>{tableau}</section>')
    contenu = (_entete("Destinataires", "Personnes qui reçoivent le rapport de veille par e-mail. Chaque destinataire "
                       "actif peut aussi se connecter au portail pour consulter le journal.")
               + formulaire + liste)
    return page("Destinataires", contenu, ctx, "destinataires", flash)


# ---------------------------------------------------------------------------------------
#  Journal
# ---------------------------------------------------------------------------------------
def page_journal(ctx: Contexte, flash: str | None, entrees: list[dict]) -> str:
    lignes = []
    for x in entrees:
        sources = x.get("sources", [])
        ok = sum(1 for s in sources if s["statut"] != "erreur")
        email = x.get("email") or {}
        if email.get("envoye"):
            info_email = f"envoyé à {pluriel(len(email.get('destinataires', [])), 'destinataire')}"
        elif email.get("erreur"):
            info_email = "envoi en échec"
        else:
            info_email = "aucun envoi"
        manuel = " · lancement manuel" if x.get("declenchement") == "manuel" else ""
        elements = "".join(
            f'<li><a href="{e(el["url"])}" target="_blank" rel="noopener">{e(el["titre"])}</a> '
            f'<span style="color:var(--doux)">— {e(el["source"])}</span></li>' for el in x.get("elements", []))
        detail_sources = "".join(
            f'<li><span class="badge {"ok" if s["statut"] != "erreur" else "erreur"}">'
            f'{"Vérifiée" if s["statut"] != "erreur" else "Échec"}</span> <strong>{e(s["nom"])}</strong> — {e(s["detail"])}</li>'
            for s in sources)
        morceaux = []
        if elements:
            morceaux.append(f"<h3>Nouveautés</h3><ul>{elements}</ul>")
        if x.get("rapport"):
            morceaux.append(f'<div><a class="btn secondaire petit" href="/rapports/{e(x["id"])}">Lire le rapport complet</a></div>')
        morceaux.append(f'<h3>Sources</h3><ul style="list-style:none;padding:0">{detail_sources}</ul>')
        if x.get("ecartes"):
            morceaux.append("<h3>Écartés après analyse</h3><ul>" + "".join(f"<li>{e(t)}</li>" for t in x["ecartes"]) + "</ul>")
        if email.get("erreur"):
            morceaux.append(f'<div class="bandeau erreur">Envoi en échec : {e(email["erreur"])}</div>')
        if x.get("remarque"):
            morceaux.append(f'<div class="bandeau alerte">{e(x["remarque"])}</div>')
        lignes.append(f"""<details class="execution"><summary><span class="quand">{e(_quand(x.get("date")))}</span>
{_badge_statut(x)}<span class="info-ligne">{ok}/{len(sources)} sources vérifiées · {e(info_email)}{manuel}</span></summary>
<div class="detail">{''.join(morceaux)}</div></details>""")
    liste = "".join(lignes) or '<div class="vide">Aucune vérification enregistrée pour le moment.</div>'
    legende = ('<div class="bandeau neutre" style="background:var(--surface)"><strong>RAS</strong> (rien à signaler) : '
               'toutes les sources ont été vérifiées et aucune nouveauté n\'a été trouvée ; aucun e-mail n\'est envoyé ce jour-là. '
               '<strong>Incomplète</strong> : au moins une source n\'a pas répondu, l\'administrateur est prévenu.</div>')
    contenu = (_entete("Journal des vérifications", "Historique des vérifications quotidiennes (7h00, heure d'Alger) "
                       "et des lancements manuels.")
               + legende + f'<section class="carte">{liste}</section>')
    return page("Journal", contenu, ctx, "journal", flash)


# ---------------------------------------------------------------------------------------
#  Sources
# ---------------------------------------------------------------------------------------
TYPES_SOURCES = {"joradp": "Journal officiel (PDF)", "page": "Page web", "rss": "Flux d'actualités",
                 "google_news": "Recherche presse"}


def page_sources(ctx: Contexte, sources: list, derniere: dict | None) -> str:
    resultats = {s["id"]: s for s in (derniere or {}).get("sources", [])}
    lignes = []
    for src in sources:
        r = resultats.get(src.id)
        if not src.actif:
            etat, detail = '<span class="badge neutre">Désactivée</span>', "Adresse à confirmer avant activation."
        elif r is None:
            etat, detail = '<span class="badge neutre">En attente</span>', "Pas encore vérifiée."
        elif r["statut"] == "erreur":
            etat, detail = '<span class="badge erreur">Échec</span>', r["detail"]
        else:
            etat, detail = '<span class="badge ok">Vérifiée</span>', r["detail"]
        adresse = "joradp.dz" if src.type == "joradp" else ("news.google.com" if src.type == "google_news" else src.url)
        lignes.append(f"""<tr><td class="cellule-nom"><strong>{e(src.nom)}</strong><span>{e(TYPES_SOURCES.get(src.type, src.type))}</span></td>
<td class="mono" style="word-break:break-all" data-libelle="Adresse">{e(adresse)}</td><td data-libelle="État">{etat}</td>
<td style="min-width:260px" data-libelle="Dernier résultat">{e(detail)}</td></tr>""")
    contenu = (_entete("Sources surveillées", "Sources consultées à chaque vérification. La liste, les mots-clés et les "
                       "exclusions se règlent dans le fichier sources.yaml.")
               + f"""<section class="carte"><div class="defilement"><table class="donnees empile"><thead><tr><th>Source</th><th>Adresse</th>
<th>État</th><th>Dernier résultat</th></tr></thead><tbody>{''.join(lignes)}</tbody></table></div></section>""")
    return page("Sources", contenu, ctx, "sources")


# ---------------------------------------------------------------------------------------
#  Rapport archivé
# ---------------------------------------------------------------------------------------
def envelopper_rapport(html: str, retour: str = "/journal") -> str:
    """Ajoute un lien de retour en haut d'un rapport archivé (document e-mail complet)."""
    barre = (f'<div style="background:#0b3a50;padding:10px 16px;font:14px \'Segoe UI\',Arial,sans-serif;">'
             f'<a href="{e(retour)}" style="color:#e6f0f4;text-decoration:none;">← Retour au journal</a></div>')
    position = html.find(">", html.find("<body")) + 1 if "<body" in html else 0
    return html[:position] + barre + html[position:]
