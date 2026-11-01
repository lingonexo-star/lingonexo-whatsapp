"""E-mails : rapport quotidien, alerte technique, lien de connexion, bienvenue, test.

Mise en page à base de tableaux et de styles en ligne, pour un rendu correct dans
Outlook (bureau, web et mobile) comme dans les autres messageries.
"""

from __future__ import annotations

from datetime import date
from html import escape

from .models import Article, ElementArticle
from .textutil import date_longue_fr, pluriel

POLICE = "'Segoe UI', Arial, Helvetica, sans-serif"
MARINE = "#0b3a50"
BLEU = "#0b4f6c"
TEXTE = "#17242c"
GRIS = "#5b6b75"
BORDURE = "#dfe5e9"
FOND = "#f2f5f7"
COULEURS_IMPACT = {
    "élevé": ("#b42318", "#fdeceb"),
    "moyen": ("#a1470a", "#fdf2e3"),
    "faible": ("#067647", "#e6f5ec"),
    "à vérifier": ("#b42318", "#fdeceb"),
    "à évaluer": ("#475467", "#eef1f3"),
}
PRODUIT = "Veille réglementaire pharmaceutique"


def e(texte) -> str:
    return escape(str(texte or ""), quote=True)


def _badge(impact: str) -> str:
    texte, fond = COULEURS_IMPACT.get(impact, COULEURS_IMPACT["à évaluer"])
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;'
            f'font-weight:600;color:{texte};background:{fond};">Impact {e(impact)}</span>')


def _entete(titre: str, sous_titre: str, organisation: str) -> str:
    marque = f"{PRODUIT} · {organisation}" if organisation else f"{PRODUIT} · Algérie"
    return f"""
<tr><td style="padding:20px 32px 18px;background:{MARINE};color:#ffffff;">
  <div style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#b9d3df;">{e(marque)}</div>
  <div style="font-size:22px;font-weight:600;margin-top:8px;line-height:1.3;">{e(titre)}</div>
  {f'<div style="font-size:14px;color:#d5e5ec;margin-top:2px;">{e(sous_titre)}</div>' if sous_titre else ''}
</td></tr>"""


def _pied(texte_html: str) -> str:
    return (f'<tr><td style="padding:18px 32px 24px;font-size:12px;color:{GRIS};line-height:1.6;'
            f'border-top:1px solid {BORDURE};">{texte_html}</td></tr>')


def _bouton(texte: str, url: str) -> str:
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:6px 0 4px;"><tr>'
            f'<td style="background:{BLEU};border-radius:6px;">'
            f'<a href="{e(url)}" style="display:inline-block;padding:12px 22px;font-size:15px;font-weight:600;'
            f'color:#ffffff;text-decoration:none;font-family:{POLICE};">{e(texte)}</a></td></tr></table>')


def _document(titre: str, corps: str) -> str:
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{e(titre)}</title></head>
<body style="margin:0;padding:0;background:{FOND};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FOND};"><tr><td align="center" style="padding:28px 10px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;background:#ffffff;border:1px solid {BORDURE};font-family:{POLICE};color:{TEXTE};">
{corps}
</table></td></tr></table></body></html>"""


def _element_html(el: ElementArticle) -> str:
    t = el.trouvaille
    lignes = []
    precise = el.entree_en_vigueur not in ("", "Non précisée", "Non précisé")
    if precise or (t.source_id == "joradp" and not t.a_verifier):
        lignes.append(("Entrée en vigueur", el.entree_en_vigueur or "Non précisée"))
    if el.acteurs and el.acteurs != "Non précisé":
        lignes.append(("Acteurs concernés", el.acteurs))
    if t.autorite:
        lignes.append(("Autorité", t.autorite))
    lignes.append(("Source", t.reference or t.source_nom))
    info = "".join(
        f'<tr><td style="padding:4px 14px 4px 0;color:{GRIS};white-space:nowrap;vertical-align:top;width:140px;">{e(k)}</td>'
        f'<td style="padding:4px 0;vertical-align:top;">{e(v)}</td></tr>' for k, v in lignes)
    officiel = ""
    if t.titre and t.titre != el.titre:
        officiel = (f'<div style="font-size:12px;color:{GRIS};margin-top:12px;line-height:1.5;">'
                    f'Intitulé officiel : {e(t.titre)}</div>')
    return f"""
<tr><td style="padding:22px 32px;border-top:1px solid {BORDURE};">
  <div style="font-size:11px;color:{GRIS};text-transform:uppercase;letter-spacing:.08em;">{e(t.type_texte)} · {e(t.source_nom)}</div>
  <div style="font-size:18px;font-weight:600;line-height:1.35;margin:6px 0 8px;"><a href="{e(t.url)}" style="color:{BLEU};text-decoration:none;">{e(el.titre)}</a></div>
  <div style="margin-bottom:10px;">{_badge(el.impact)}</div>
  <p style="font-size:15px;line-height:1.6;margin:0 0 12px;">{e(el.resume)}</p>
  <table role="presentation" style="font-size:13px;line-height:1.5;border-collapse:collapse;width:100%;">{info}</table>
  {officiel}
  <div style="margin-top:12px;"><a href="{e(t.url)}" style="font-size:14px;font-weight:600;color:{BLEU};">Consulter le texte officiel</a></div>
</td></tr>"""


def _sources_html(sources: list[dict]) -> str:
    lignes = []
    for s in sources:
        ok = s["statut"] != "erreur"
        lignes.append(
            f'<tr><td style="padding:3px 10px 3px 0;color:{"#067647" if ok else "#b42318"};vertical-align:top;font-weight:600;">'
            f'{"OK" if ok else "Échec"}</td><td style="padding:3px 0;"><strong>{e(s["nom"])}</strong> — {e(s["detail"])}</td></tr>')
    return "".join(lignes)


def _mention(organisation: str, contact: str) -> str:
    phrase = "Vous recevez ce message car vous êtes inscrit(e) à la veille réglementaire"
    phrase += f" de {e(organisation)}." if organisation else "."
    if contact:
        phrase += f" Pour modifier votre inscription, contactez {e(contact)}."
    return phrase


def rendre_email(article: Article, entree: dict, jour: date, url_journal: str = "",
                 organisation: str = "", contact: str = "") -> tuple[str, str]:
    n = len(article.elements)
    sujet = f"Veille réglementaire pharma – {pluriel(n, 'nouveauté')} – {date_longue_fr(jour)}"
    avertissement = ""
    if article.avertissement:
        avertissement = (f'<tr><td style="padding:0 32px 14px;"><div style="font-size:13px;padding:10px 12px;'
                         f'background:#fdf2e3;color:#7a2e0e;">{e(article.avertissement)}</div></td></tr>')
    sommaire = "".join(
        f'<tr><td style="padding:3px 10px 3px 0;vertical-align:top;color:{GRIS};">{i}.</td>'
        f'<td style="padding:3px 0;">{e(el.titre)} <span style="color:{GRIS};">— {e(el.trouvaille.source_nom)}</span></td></tr>'
        for i, el in enumerate(article.elements, start=1))
    lien = f' <a href="{e(url_journal)}" style="color:{BLEU};">Ouvrir le portail de veille</a>.' if url_journal else ""
    corps = (
        _entete(f"Note de veille du {date_longue_fr(jour)}", pluriel(n, "nouveauté") + " ce matin", organisation)
        + f'<tr><td style="padding:24px 32px 6px;font-size:15px;line-height:1.65;">{e(article.chapeau)}</td></tr>'
        + (f'<tr><td style="padding:10px 32px 18px;"><div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
           f'color:{GRIS};margin-bottom:6px;">Au sommaire</div><table role="presentation" style="font-size:14px;'
           f'line-height:1.5;border-collapse:collapse;">{sommaire}</table></td></tr>' if n > 1 else "")
        + avertissement
        + "".join(_element_html(el) for el in article.elements)
        + f'<tr><td style="padding:18px 32px;border-top:1px solid {BORDURE};background:#f7f9fa;">'
          f'<div style="font-size:12px;font-weight:600;margin-bottom:6px;text-transform:uppercase;letter-spacing:.08em;color:{GRIS};">'
          f'Sources vérifiées</div><table role="presentation" style="font-size:13px;line-height:1.5;border-collapse:collapse;">'
          f'{_sources_html(entree["sources"])}</table></td></tr>'
        + _pied(f"Résumés établis automatiquement à partir des publications officielles : seul le texte publié fait foi."
                f"{lien}<br>{_mention(organisation, contact)}")
    )
    return sujet, _document(sujet, corps)


def rendre_alerte(entree: dict, jour: date, url_journal: str = "", organisation: str = "") -> tuple[str, str]:
    en_erreur = [s for s in entree["sources"] if s["statut"] == "erreur"]
    sujet = f"Veille pharma : vérification incomplète – {date_longue_fr(jour)}"
    lien = _bouton("Ouvrir le portail", url_journal) if url_journal else ""
    email = entree.get("email") or {}
    probleme_email = (f'<p style="margin:0 0 12px;"><strong>Envoi du rapport en échec :</strong> {e(email["erreur"])}</p>'
                      if email.get("erreur") else "")
    corps = (
        _entete("Vérification incomplète", date_longue_fr(jour).capitalize(), organisation)
        + f"""<tr><td style="padding:24px 32px;font-size:15px;line-height:1.6;">
  <p style="margin:0 0 12px;">Message destiné à l'administrateur de la veille. {pluriel(len(en_erreur), 'source n’a', 'sources n’ont')}
  pas pu être vérifiée(s) ce matin. Tant que le problème persiste, l'absence de rapport ne garantit pas l'absence de nouveauté pour ces sources.</p>
  {probleme_email}
  <table role="presentation" style="font-size:14px;line-height:1.5;border-collapse:collapse;margin-bottom:12px;">{_sources_html(en_erreur)}</table>
  {lien}
</td></tr>"""
        + _pied("Si l'erreur se répète plusieurs jours, l'adresse du site a probablement changé : "
                "corrigez-la dans le fichier sources.yaml, ou désactivez la source.")
    )
    return sujet, _document(sujet, corps)


def rendre_message(sujet: str, titre: str, paragraphes: list[str], bouton: tuple[str, str] | None = None,
                   note: str = "", organisation: str = "") -> tuple[str, str]:
    """Message simple : lien de connexion, bienvenue, test d'envoi."""
    texte = "".join(f'<p style="margin:0 0 14px;">{e(p)}</p>' for p in paragraphes)
    corps = (
        _entete(titre, "", organisation)
        + f'<tr><td style="padding:24px 32px 18px;font-size:15px;line-height:1.6;">{texte}'
          f'{_bouton(*bouton) if bouton else ""}</td></tr>'
        + (_pied(e(note)) if note else "")
    )
    return sujet, _document(sujet, corps)


# --------------------------------------------------------------------------------------
#  Version Markdown de la note (lisible directement sur GitHub)
# --------------------------------------------------------------------------------------
def _md(texte) -> str:
    """Neutralise les caractères qui casseraient un tableau ou un lien Markdown."""
    return str(texte or "").replace("|", "/").replace("\n", " ").replace("[", "(").replace("]", ")")


def rendre_markdown(article: Article, entree: dict, jour: date) -> str:
    n = len(article.elements)
    lignes = [f"# Note de veille du {date_longue_fr(jour)}", "", f"**{pluriel(n, 'nouveauté')}.** {_md(article.chapeau)}", ""]
    if article.avertissement:
        lignes += [f"> {_md(article.avertissement)}", ""]
    for i, el in enumerate(article.elements, start=1):
        t = el.trouvaille
        lignes += [f"## {i}. {_md(el.titre)}", "",
                   f"*{_md(t.type_texte)} · {_md(t.source_nom)}* — **Impact {_md(el.impact)}**", "",
                   _md(el.resume), ""]
        if el.entree_en_vigueur:
            lignes.append(f"- **Entrée en vigueur :** {_md(el.entree_en_vigueur)}")
        if el.acteurs and el.acteurs != "Non précisé":
            lignes.append(f"- **Acteurs concernés :** {_md(el.acteurs)}")
        if t.autorite:
            lignes.append(f"- **Autorité :** {_md(t.autorite)}")
        lignes += [f"- **Source :** {_md(t.reference or t.source_nom)}", f"- **Texte officiel :** [consulter]({t.url})", ""]
        if t.titre and t.titre != el.titre:
            lignes += [f"> Intitulé officiel : {_md(t.titre)}", ""]
    lignes += ["---", "", "**Sources vérifiées**", ""]
    lignes += [f"- {'✅' if s['statut'] != 'erreur' else '⚠️'} {_md(s['nom'])} — {_md(s['detail'])}" for s in entree["sources"]]
    lignes += ["", "*Résumés établis automatiquement : seul le texte officiel fait foi.*", ""]
    return "\n".join(lignes)
