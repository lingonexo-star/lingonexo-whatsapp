"""Rédaction de l'article : résumé clair de chaque nouveauté.

- Avec Azure OpenAI (recommandé) : résumé rédigé, impact, entrée en vigueur,
  et élimination des faux positifs.
- Sans IA : on reprend l'article 1er du texte officiel (ou l'extrait publié).
Les liens viennent toujours des sources, jamais de l'IA.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from .config import Parametres
from .http import ClientHttp
from .models import Article, ElementArticle, Trouvaille
from .textutil import couper, date_longue_fr, normaliser, pluriel

journal = logging.getLogger(__name__)

ORDRE_IMPACT = {"élevé": 0, "moyen": 1, "faible": 2, "à vérifier": 0, "à évaluer": 3}

CONSIGNE_ELEMENTS = """Tu es analyste en veille réglementaire pour l'industrie pharmaceutique en Algérie \
(fabricants, importateurs, distributeurs, officines). On te transmet des textes détectés \
automatiquement (Journal officiel, sites des ministères, presse).

Pour chaque élément :
- « pertinent » : true seulement s'il concerne réellement la réglementation du médicament, des \
produits pharmaceutiques, des dispositifs médicaux ou des établissements pharmaceutiques en Algérie. \
Une nomination, un virement de crédits, une activité protocolaire ou une actualité sans portée \
réglementaire n'est PAS pertinente.
- « titre » : titre court et clair en français (12 mots maximum).
- « resume » : 2 à 4 phrases simples et factuelles : ce que dit le texte, qui est concerné, ce qui change.
- « entree_en_vigueur » : la date ou la règle d'entrée en vigueur si elle figure dans le texte, sinon « Non précisée ».
- « acteurs » : les acteurs concernés (ex. fabricants, importateurs, officines), sinon « Non précisé ».
- « impact » : « élevé », « moyen » ou « faible » pour un établissement pharmaceutique.

Règles : n'invente rien, n'utilise que les informations fournies, ne mets aucun lien.
Réponds uniquement en JSON, au format :
{"elements": [{"id": "...", "pertinent": true, "titre": "...", "resume": "...", \
"entree_en_vigueur": "...", "acteurs": "...", "impact": "moyen"}]}"""

CONSIGNE_CHAPEAU = """Tu rédiges le chapeau (introduction) d'une note quotidienne de veille réglementaire \
sur l'industrie pharmaceutique en Algérie. En 2 ou 3 phrases, ton professionnel et simple, présente \
l'essentiel des nouveautés listées, en commençant par la plus importante. N'invente rien, pas de \
formule de politesse, pas de lien. Réponds uniquement en JSON : {"chapeau": "..."}"""


def _impact(valeur: str | None) -> str:
    n = normaliser(valeur or "")
    if n.startswith("elev") or n.startswith("haut"):
        return "élevé"
    if n.startswith("moy"):
        return "moyen"
    if n.startswith("faib") or n.startswith("bas"):
        return "faible"
    return "à évaluer"


def _trier(elements: list[ElementArticle]) -> list[ElementArticle]:
    return sorted(elements, key=lambda e: (
        ORDRE_IMPACT.get(e.impact, 3), e.trouvaille.categorie != "officielle"))


class RedacteurSimple:
    """Sans IA : reprend fidèlement le texte officiel."""

    mode = "simple"

    def titre(self, t: Trouvaille) -> str:
        if t.source_id == "joradp" and not t.a_verifier:
            from .sources.joradp import analyser_titre

            objet = analyser_titre(t.titre)["objet"]
            if objet:
                return couper(f"{t.type_texte} {objet}", 160)
        return couper(t.titre, 160)

    def element(self, t: Trouvaille) -> ElementArticle:
        return ElementArticle(
            trouvaille=t,
            titre=self.titre(t),
            resume=t.extrait or "Voir le texte officiel.",
            impact="à vérifier" if t.a_verifier else "à évaluer",
        )

    def chapeau(self, elements: list[ElementArticle], jour: date) -> str:
        officiels = sum(1 for e in elements if e.trouvaille.source_id == "joradp")
        ministeres = sum(1 for e in elements
                         if e.trouvaille.source_id != "joradp" and e.trouvaille.categorie == "officielle")
        presse = sum(1 for e in elements if e.trouvaille.categorie == "presse")
        parties = []
        if officiels:
            parties.append(f"{officiels} au Journal officiel")
        if ministeres:
            parties.append(f"{ministeres} sur les sites officiels")
        if presse:
            parties.append(f"{presse} dans la presse")
        return (f"La veille du {date_longue_fr(jour)} a relevé "
                f"{pluriel(len(elements), 'nouveauté')} concernant la réglementation pharmaceutique "
                f"en Algérie ({', '.join(parties)}). Le détail et les liens vers les textes "
                "officiels figurent ci-dessous.")

    def rediger(self, trouvailles: list[Trouvaille], jour: date) -> Article:
        elements = _trier([self.element(t) for t in trouvailles])
        return Article(chapeau=self.chapeau(elements, jour), elements=elements, mode=self.mode)


class RedacteurIA(RedacteurSimple):
    """Azure OpenAI (service Microsoft) : article rédigé et faux positifs écartés."""

    mode = "ia"
    TAILLE_LOT = 6

    def __init__(self, http: ClientHttp, parametres: Parametres):
        self.http = http
        self.p = parametres

    def _appeler(self, consigne: str, contenu: dict) -> dict:
        corps = {
            "messages": [
                {"role": "system", "content": consigne},
                {"role": "user", "content": json.dumps(contenu, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
        }
        if self.p.aoai_endpoint:  # Azure OpenAI
            url = (f"{self.p.aoai_endpoint.rstrip('/')}/openai/deployments/{self.p.aoai_deploiement}"
                   f"/chat/completions?api-version={self.p.aoai_version}")
            entetes = {"api-key": self.p.aoai_cle}
        else:  # API compatible OpenAI (ex. Gemini)
            url = self.p.ia_url
            entetes = {"Authorization": f"Bearer {self.p.ia_cle}"}
            corps["model"] = self.p.ia_modele
        reponse = self.http.post(url, headers={**entetes, "Content-Type": "application/json"}, json=corps, timeout=120)
        if reponse.status_code != 200:
            raise RuntimeError(f"Le service d'IA a répondu {reponse.status_code} : {reponse.text[:300]}")
        texte = reponse.json()["choices"][0]["message"]["content"].strip()
        if texte.startswith("```"):  # certaines IA entourent le JSON de balises de code
            texte = texte.strip("`").removeprefix("json").strip()
        return json.loads(texte)

    def rediger(self, trouvailles: list[Trouvaille], jour: date) -> Article:
        a_resumer = [t for t in trouvailles if not t.a_verifier]
        reponses: dict[str, dict] = {}
        erreurs: list[str] = []
        for debut in range(0, len(a_resumer), self.TAILLE_LOT):
            lot = a_resumer[debut: debut + self.TAILLE_LOT]
            try:
                resultat = self._appeler(CONSIGNE_ELEMENTS, {"elements": [{
                    "id": t.id, "source": t.source_nom, "type": t.type_texte,
                    "reference": t.reference, "autorite": t.autorite,
                    "titre_officiel": t.titre, "texte": t.texte or t.extrait,
                } for t in lot]})
                for item in resultat.get("elements") or []:
                    if isinstance(item, dict) and item.get("id"):
                        reponses[str(item["id"])] = item
            except Exception as exc:
                journal.warning("Résumé IA impossible pour un lot", exc_info=True)
                erreurs.append(str(exc))

        elements: list[ElementArticle] = []
        ecartes: list[str] = []
        for t in trouvailles:
            item = reponses.get(t.id)
            if t.a_verifier or item is None:
                elements.append(self.element(t))
            elif item.get("pertinent") is False:
                ecartes.append(t.titre)
            else:
                elements.append(ElementArticle(
                    trouvaille=t,
                    titre=couper(str(item.get("titre") or self.titre(t)), 160),
                    resume=str(item.get("resume") or t.extrait or "Voir le texte officiel."),
                    impact=_impact(item.get("impact")),
                    entree_en_vigueur=str(item.get("entree_en_vigueur") or "Non précisée"),
                    acteurs=str(item.get("acteurs") or ""),
                ))
        elements = _trier(elements)

        chapeau = self.chapeau(elements, jour) if elements else ""
        if elements:
            try:
                resultat = self._appeler(CONSIGNE_CHAPEAU, {"date": date_longue_fr(jour), "nouveautes": [
                    {"titre": e.titre, "resume": e.resume, "impact": e.impact, "source": e.trouvaille.source_nom}
                    for e in elements]})
                chapeau = str(resultat.get("chapeau") or chapeau)
            except Exception as exc:
                journal.warning("Chapeau IA impossible", exc_info=True)
                erreurs.append(str(exc))

        return Article(
            chapeau=chapeau, elements=elements, ecartes=ecartes,
            mode="ia-partiel" if erreurs else "ia",
            avertissement=("Le résumé automatique n'a pas fonctionné pour une partie des éléments : "
                           "leur extrait officiel est repris tel quel.") if erreurs else None,
        )


def construire_redacteur(http: ClientHttp, parametres: Parametres) -> RedacteurSimple:
    return RedacteurIA(http, parametres) if parametres.ia_active else RedacteurSimple()
