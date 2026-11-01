"""Mise en forme : e-mail (article), alerte technique et page « journal » (RAS)."""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from urllib.parse import quote

from .models import Article, ElementArticle
from .textutil import date_longue_fr, pluriel

POLICE = "'Segoe UI', Arial, Helvetica, sans-serif"
BLEU = "#0b4f6c"
GRIS = "#52606d"
BORDURE = "#e4e8ec"
COULEURS_IMPACT = {
    "élevé": ("#b42318", "#fef3f2"),
    "moyen": ("#b54708", "#fffaeb"),
    "faible": ("#067647", "#ecfdf3"),
    "à vérifier": ("#b42318", "#fef3f2"),
    "à évaluer": ("#475467", "#f2f4f7"),
}


def e(texte) -> str:
    return escape(str(texte or ""), quote=True)


def _badge(impact: str) -> str:
    texte, fond = COULEURS_IMPACT.get(impact, COULEURS_IMPACT["à évaluer"])
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;'
            f'font-weight:600;color:{texte};background:{fond};">Impact : {e(impact)}</span>')


def _element_html(el: ElementArticle) -> str:
    t = el.trouvaille
    lignes_info = []
    precise = el.entree_en_vigueur not in ("", "Non précisée", "Non précisé")
    if precise or (t.source_id == "joradp" and not t.a_verifier):
        lignes_info.append(("Entrée en vigueur", el.entree_en_vigueur or "Non précisée"))
    if el.acteurs and el.acteurs != "Non précisé":
        lignes_info.append(("Acteurs concernés", el.acteurs))
    if t.autorite:
        lignes_info.append(("Autorité", t.autorite))
    info = "".join(
        f'<tr><td style="padding:3px 12px 3px 0;color:{GRIS};white-space:nowrap;vertical-align:top;">{e(k)}</td>'
        f'<td style="padding:3px 0;">{e(v)}</td></tr>' for k, v in lignes_info)
    titre_officiel = ""
    if t.titre and t.titre != el.titre:
        titre_officiel = (f'<div style="font-size:12px;color:{GRIS};margin-top:10px;line-height:1.5;">'
                          f'<em>Intitulé officiel :</em> {e(t.titre)}</div>')
    return f"""
<tr><td style="padding:20px 28px;border-top:1px solid {BORDURE};">
  <div style="font-size:12px;color:{GRIS};text-transform:uppercase;letter-spacing:.05em;">{e(t.type_texte)} · {e(t.source_nom)}</div>
  <div style="font-size:18px;font-weight:600;line-height:1.35;margin:6px 0 6px;"><a href="{e(t.url)}" style="color:{BLEU};text-decoration:none;">{e(el.titre)}</a></div>
  <div style="margin-bottom:10px;">{_badge(el.impact)} <span style="font-size:13px;color:{GRIS};">&nbsp;{e(t.reference)}</span></div>
  <p style="font-size:15px;line-height:1.6;margin:0 0 10px;">{e(el.resume)}</p>
  {f'<table role="presentation" style="font-size:13px;line-height:1.5;border-collapse:collapse;">{info}</table>' if info else ''}
  {titre_officiel}
  <div style="margin-top:12px;"><a href="{e(t.url)}" style="font-size:14px;font-weight:600;color:{BLEU};">Lire le texte officiel →</a></div>
</td></tr>"""


def _sources_html(sources: list[dict]) -> str:
    lignes = []
    for s in sources:
        ok = s["statut"] != "erreur"
        symbole = "✓" if ok else "⚠"
        couleur = "#067647" if ok else "#b42318"
        lignes.append(
            f'<tr><td style="padding:3px 8px 3px 0;color:{couleur};vertical-align:top;">{symbole}</td>'
            f'<td style="padding:3px 0;"><strong>{e(s["nom"])}</strong> — {e(s["detail"])}</td></tr>')
    return "".join(lignes)


def _document(titre: str, corps: str) -> str:
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(titre)}</title></head>
<body style="margin:0;padding:0;background:#f3f5f7;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f5f7;"><tr><td align="center" style="padding:24px 10px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;background:#ffffff;border:1px solid {BORDURE};border-radius:8px;font-family:{POLICE};color:#1f2933;">
{corps}
</table></td></tr></table></body></html>"""


def rendre_email(article: Article, entree: dict, jour: date, url_journal: str = "") -> tuple[str, str]:
    n = len(article.elements)
    sujet = f"Veille réglementaire pharma – {pluriel(n, 'nouveauté')} – {date_longue_fr(jour)}"
    avertissement = ""
    if article.avertissement:
        avertissement = (f'<tr><td style="padding:0 28px 12px;"><div style="font-size:13px;padding:10px 12px;'
                         f'background:#fffaeb;border-radius:6px;color:#7a2e0e;">{e(article.avertissement)}</div></td></tr>')
    lien_journal = (f' Journal des vérifications : <a href="{e(url_journal)}" style="color:{BLEU};">ouvrir</a>.'
                    if url_journal else "")
    corps = f"""
<tr><td style="padding:22px 28px;background:{BLEU};color:#ffffff;border-radius:8px 8px 0 0;">
  <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.85;">Veille réglementaire · Industrie pharmaceutique · Algérie</div>
  <div style="font-size:22px;font-weight:600;margin-top:6px;">{e(pluriel(n, 'nouveauté'))}</div>
  <div style="font-size:14px;opacity:.9;margin-top:2px;">{e(date_longue_fr(jour).capitalize())}</div>
</td></tr>
<tr><td style="padding:22px 28px 14px;font-size:15px;line-height:1.65;">{e(article.chapeau)}</td></tr>
{avertissement}
{''.join(_element_html(el) for el in article.elements)}
<tr><td style="padding:18px 28px;border-top:1px solid {BORDURE};background:#f8fafb;">
  <div style="font-size:13px;font-weight:600;margin-bottom:6px;">Sources vérifiées ce matin</div>
  <table role="presentation" style="font-size:13px;line-height:1.5;border-collapse:collapse;">{_sources_html(entree['sources'])}</table>
</td></tr>
<tr><td style="padding:16px 28px 22px;font-size:12px;color:{GRIS};line-height:1.6;">
  Message automatique de la veille réglementaire quotidienne. Les résumés sont rédigés automatiquement :
  seul le texte officiel fait foi.{lien_journal}
</td></tr>"""
    return sujet, _document(sujet, corps)


def rendre_alerte(entree: dict, jour: date, url_journal: str = "") -> tuple[str, str]:
    en_erreur = [s for s in entree["sources"] if s["statut"] == "erreur"]
    sujet = f"⚠ Veille pharma : vérification incomplète – {date_longue_fr(jour)}"
    lien = f'<p><a href="{e(url_journal)}" style="color:{BLEU};">Ouvrir le journal</a></p>' if url_journal else ""
    corps = f"""
<tr><td style="padding:22px 28px;font-size:15px;line-height:1.6;">
  <div style="font-size:18px;font-weight:600;color:#b42318;margin-bottom:8px;">Vérification incomplète</div>
  <p>Ce matin, {pluriel(len(en_erreur), 'source n’a', 'sources n’ont')} pas pu être vérifiée(s).
  Tant que le problème persiste, l’absence de message ne garantit pas l’absence de nouveauté pour cette source.</p>
  <table role="presentation" style="font-size:14px;line-height:1.5;border-collapse:collapse;">{_sources_html(en_erreur)}</table>
  {lien}
  <p style="font-size:12px;color:{GRIS};">Si l’erreur se répète plusieurs jours, l’adresse du site a probablement changé :
  corrigez-la dans le fichier sources.yaml (ou désactivez la source).</p>
</td></tr>"""
    return sujet, _document(sujet, corps)


# --------------------------------------------------------------------------------------
#  Page « journal » : l'utilisateur vérifie que la veille a bien tourné (RAS ou non).
# --------------------------------------------------------------------------------------
LIBELLES = {
    "RAS": ("RAS", "ras", "Rien à signaler : toutes les sources ont été vérifiées, aucune nouveauté."),
    "NOUVEAUTES": ("Nouveautés", "new", "Des nouveautés ont été trouvées et envoyées par e-mail."),
    "INCOMPLET": ("Vérification incomplète", "warn", "Au moins une source n'a pas pu être vérifiée."),
}

_CSS = """
:root{--fond:#f4f6f8;--carte:#fff;--texte:#1f2933;--doux:#52606d;--bord:#e4e8ec;--accent:#0b4f6c;
--ras:#067647;--ras-f:#ecfdf3;--new:#175cd3;--new-f:#eff8ff;--warn:#b54708;--warn-f:#fffaeb;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--fond:#0f1720;--carte:#16212c;--texte:#e6edf3;--doux:#9fb0c0;
--bord:#263544;--accent:#6cc3e8;--ras:#4ade80;--ras-f:#0f2a1c;--new:#7cb7ff;--new-f:#0f2140;--warn:#fbbf24;
--warn-f:#2f230a;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--fond);color:var(--texte);
font:15px/1.55 'Segoe UI',system-ui,-apple-system,Arial,sans-serif}
main{max-width:860px;margin:0 auto;padding:28px 16px 48px}
h1{font-size:24px;margin:0 0 4px}.sous{color:var(--doux);margin:0 0 20px}
.carte{background:var(--carte);border:1px solid var(--bord);border-radius:10px;padding:18px 20px;margin-bottom:16px}
.etat{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.etat .gros{font-size:30px;font-weight:700;padding:2px 14px;border-radius:8px}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:13px;font-weight:600}
.ras{color:var(--ras);background:var(--ras-f)}.new{color:var(--new);background:var(--new-f)}
.warn{color:var(--warn);background:var(--warn-f)}
details{border-top:1px solid var(--bord)}details:first-of-type{border-top:0}
summary{cursor:pointer;padding:12px 0;display:flex;gap:12px;align-items:center;flex-wrap:wrap;list-style:none}
summary::-webkit-details-marker{display:none}summary .quand{min-width:190px;font-weight:600}
summary .info{color:var(--doux);font-size:14px}.detail{padding:0 0 14px 4px;font-size:14px}
.detail ul{margin:6px 0;padding-left:20px}.detail ul.sources{list-style:none;padding-left:4px}.detail li{margin:3px 0}a{color:var(--accent)}
button{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--accent);background:var(--accent);
color:var(--carte);cursor:pointer}.doux{color:var(--doux);font-size:13px}
"""


def _lien(base: str, code: str, **params) -> str:
    morceaux = [f"{k}={quote(str(v))}" for k, v in params.items()]
    if code:
        morceaux.append(f"code={quote(code)}")
    return base + ("?" + "&".join(morceaux) if morceaux else "")


def _quand(entree: dict) -> str:
    try:
        d = datetime.fromisoformat(entree["date"])
        return f"{date_longue_fr(d.date()).capitalize()} à {d:%H:%M}"
    except Exception:
        return entree.get("id", "")


def rendre_journal(entrees: list[dict], code: str = "", lancer_possible: bool = True) -> str:
    if entrees:
        derniere = entrees[0]
        libelle, classe, explication = LIBELLES.get(derniere["statut"], LIBELLES["INCOMPLET"])
        if derniere["statut"] == "NOUVEAUTES":
            libelle = pluriel(derniere.get("nb_nouveautes", 0), "nouveauté")
        resume = f"""<div class="carte"><div class="doux">Dernière vérification</div>
<div class="etat"><span class="gros {classe}">{e(libelle)}</span>
<span>{e(_quand(derniere))}<br><span class="doux">{e(explication)}</span></span></div></div>"""
    else:
        resume = '<div class="carte">Aucune vérification enregistrée pour le moment.</div>'

    lignes = []
    for entree in entrees:
        libelle, classe, _ = LIBELLES.get(entree["statut"], LIBELLES["INCOMPLET"])
        if entree["statut"] == "NOUVEAUTES":
            libelle = pluriel(entree.get("nb_nouveautes", 0), "nouveauté")
        sources = entree.get("sources", [])
        ok = sum(1 for s in sources if s["statut"] != "erreur")
        email = entree.get("email") or {}
        info_email = "e-mail envoyé" if email.get("envoye") else ("e-mail NON envoyé" if email.get("erreur") else "aucun e-mail (RAS)")
        items = "".join(
            f'<li><a href="{e(x["url"])}">{e(x["titre"])}</a> <span class="doux">— {e(x["source"])}</span></li>'
            for x in entree.get("elements", []))
        rapport = (f'<p><a href="{e(_lien("rapport", code, id=entree["id"]))}">Lire l\'article complet</a></p>'
                   if entree.get("rapport") else "")
        ecartes = ""
        if entree.get("ecartes"):
            ecartes = ("<p class='doux'>Écartés après analyse (hors sujet) : "
                       + "; ".join(e(x) for x in entree["ecartes"]) + "</p>")
        erreur_email = f"<p class='doux'>Problème d'envoi : {e(email['erreur'])}</p>" if email.get("erreur") else ""
        remarque = f"<p class='doux'>{e(entree['remarque'])}</p>" if entree.get("remarque") else ""
        detail_sources = "".join(
            f"<li>{'✓' if s['statut'] != 'erreur' else '⚠'} <strong>{e(s['nom'])}</strong> — {e(s['detail'])}</li>"
            for s in sources)
        lignes.append(f"""<details>
<summary><span class="quand">{e(_quand(entree))}</span><span class="badge {classe}">{e(libelle)}</span>
<span class="info">{ok}/{len(sources)} sources vérifiées · {e(info_email)}{' · lancement manuel' if entree.get('declenchement') == 'manuel' else ''}</span></summary>
<div class="detail">{f'<ul>{items}</ul>' if items else ''}{rapport}<div class="doux">Sources :</div><ul class="sources">{detail_sources}</ul>{ecartes}{erreur_email}{remarque}</div>
</details>""")

    bouton = ""
    if lancer_possible:
        bouton = (f'<form method="post" action="{e(_lien("lancer", code))}" '
                  'onsubmit="this.querySelector(\'button\').disabled=true;this.querySelector(\'button\').textContent=\'Vérification en cours… (1 à 3 min)\'">'
                  '<button type="submit">Lancer une vérification maintenant</button></form>')

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Journal de veille</title>
<style>{_CSS}</style></head><body><main>
<h1>Journal de la veille réglementaire</h1>
<p class="sous">Industrie pharmaceutique · Algérie — vérification automatique chaque matin à 7h00 (heure d'Alger).
<strong>RAS</strong> signifie que toutes les sources ont été vérifiées et qu'il n'y a rien de nouveau.</p>
{resume}
<div class="carte">{''.join(lignes) or '<p class="doux">Pas encore d’historique.</p>'}</div>
{bouton}
</main></body></html>"""
