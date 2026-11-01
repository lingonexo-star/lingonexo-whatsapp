"""Scénario complet : plusieurs matins de suite, avec et sans nouveautés."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from veille.config import charger_configuration
from veille.mailer import ExpediteurFichier
from veille.ui import Contexte, page_journal
from veille.runner import executer, lire_journal
from veille.storage import StockageLocal
from veille.summarize import RedacteurIA

from conftest import FausseReponse
from test_web import NOUVEAU, PAGE, RSS

ALGER = ZoneInfo("Africa/Algiers")
JO = "https://www.joradp.dz/FTP/jo-francais/2026/F2026{:03d}.pdf"


def matin(jour):
    return datetime(2026, 11, jour, 7, 0, 0, tzinfo=ALGER)


def internet(faux_http, pdf, parametres):
    """Les sites tels qu'ils sont le premier matin."""
    for n in range(1, 58):
        faux_http.ajouter(JO.format(n), pdf, "application/pdf")
    faux_http.ajouter("https://www.miph.gov.dz/fr/feed/", RSS.format(nouveau=""), "application/rss+xml")
    faux_http.ajouter("https://www.commerce.gov.dz/fr", PAGE.format(nouveau=""))
    faux_http.ajouter("https://www.industrie.gov.dz", PAGE.format(nouveau=""))
    presse = next(c for c in charger_configuration(parametres.fichier_sources).sources if c.id == "presse")
    faux_http.ajouter(presse.url, RSS.format(nouveau=""), "application/rss+xml")


def lancer(parametres, faux_http, stockage, expediteur, jour, **options):
    return executer(parametres, http=faux_http, stockage=stockage, expediteur=expediteur,
                    maintenant=matin(jour), **options)


def test_plusieurs_matins(parametres, faux_http, pdf_jo, pdf_jo_vide):
    stockage = StockageLocal(parametres.dossier_donnees)
    expediteur = ExpediteurFichier(stockage)
    internet(faux_http, pdf_jo_vide, parametres)

    # Matin 1 : première vérification -> RAS, aucun e-mail.
    j1 = lancer(parametres, faux_http, stockage, expediteur, 1)
    assert j1["statut"] == "RAS"
    assert {s["statut"] for s in j1["sources"]} == {"initialisation"}
    assert expediteur.envoyes == []

    # Matin 2 : rien de nouveau -> RAS, aucun e-mail.
    j2 = lancer(parametres, faux_http, stockage, expediteur, 2)
    assert j2["statut"] == "RAS" and expediteur.envoyes == []

    # Matin 3 : un nouveau JO pharmaceutique + un arrêté sur le site du Commerce -> e-mail.
    faux_http.ajouter(JO.format(58), pdf_jo, "application/pdf")
    faux_http.ajouter("https://www.commerce.gov.dz/fr", PAGE.format(nouveau=NOUVEAU))
    j3 = lancer(parametres, faux_http, stockage, expediteur, 3)
    assert j3["statut"] == "NOUVEAUTES" and j3["nb_nouveautes"] == 3
    assert j3["email"]["envoye"] and j3["email"]["destinataires"] == ["veille@exemple.dz"]
    assert len(expediteur.envoyes) == 1
    mail = expediteur.envoyes[0]
    assert mail["sujet"] == "Veille réglementaire pharma – 3 nouveautés – mardi 3 novembre 2026"
    assert "Consulter le texte officiel" in mail["html"]
    assert JO.format(58) + "#page=2" in mail["html"]
    assert stockage.lire_texte(j3["rapport"]) == mail["html"]

    # Matin 4 : déjà signalé -> RAS, pas de doublon.
    j4 = lancer(parametres, faux_http, stockage, expediteur, 4)
    assert j4["statut"] == "RAS" and len(expediteur.envoyes) == 1

    # Matin 5 : un site est en panne -> « vérification incomplète », alerte technique.
    faux_http.en_panne.add("https://www.industrie.gov.dz")
    j5 = lancer(parametres, faux_http, stockage, expediteur, 5)
    assert j5["statut"] == "INCOMPLET"
    assert expediteur.envoyes[-1]["destinataires"] == ["it@exemple.dz"]
    assert "Vérification incomplète" in expediteur.envoyes[-1]["html"]

    # Le journal permet de vérifier chaque matin.
    entrees = lire_journal(stockage)
    assert [x["statut"] for x in entrees] == ["INCOMPLET", "RAS", "NOUVEAUTES", "RAS", "RAS"]
    page = page_journal(Contexte("veille@exemple.dz", "lecteur", "j"), None, entrees)
    assert "RAS" in page and "Incomplète" in page
    assert 'href="/rapports/2026-11-03T07-00-00"' in page


def test_echec_email_resignale_le_lendemain(parametres, faux_http, pdf_jo, pdf_jo_vide):
    stockage = StockageLocal(parametres.dossier_donnees)
    internet(faux_http, pdf_jo_vide, parametres)
    lancer(parametres, faux_http, stockage, ExpediteurFichier(stockage), 1)
    faux_http.ajouter(JO.format(58), pdf_jo, "application/pdf")

    class EnPanne:
        def envoyer(self, *a):
            raise RuntimeError("serveur de messagerie indisponible")

    j2 = lancer(parametres, faux_http, stockage, EnPanne(), 2)
    assert j2["statut"] == "NOUVEAUTES" and not j2["email"]["envoye"]
    assert "serveur de messagerie" in j2["email"]["erreur"]
    ok = ExpediteurFichier(stockage)
    j3 = lancer(parametres, faux_http, stockage, ok, 3)
    assert j3["email"]["envoye"] and len(ok.envoyes) == 1  # les nouveautés sont renvoyées


def test_redaction_par_azure_openai(parametres, faux_http, pdf_jo, pdf_jo_vide):
    stockage = StockageLocal(parametres.dossier_donnees)
    internet(faux_http, pdf_jo_vide, parametres)
    lancer(parametres, faux_http, stockage, ExpediteurFichier(stockage), 1)
    faux_http.ajouter(JO.format(58), pdf_jo, "application/pdf")
    parametres.aoai_endpoint = "https://exemple.openai.azure.com/"
    parametres.aoai_cle = "cle"
    parametres.aoai_deploiement = "gpt-mini"

    def repondre(url, options):
        assert url.startswith("https://exemple.openai.azure.com/openai/deployments/gpt-mini/chat/completions")
        demande = json.loads(options["json"]["messages"][1]["content"])
        if "elements" in demande:
            items = []
            for el in demande["elements"]:
                pertinent = "Arrêté" not in el["type"]
                items.append({"id": el["id"], "pertinent": pertinent, "titre": "Enregistrement des médicaments : nouvelle procédure",
                              "resume": "Le dépôt devient électronique.", "entree_en_vigueur": "Six mois après publication",
                              "acteurs": "Fabricants, importateurs", "impact": "Élevé"})
            contenu = {"elements": items}
        else:
            contenu = {"chapeau": "Une réforme majeure de l'enregistrement est publiée."}
        corps = {"choices": [{"message": {"content": json.dumps(contenu, ensure_ascii=False)}}]}
        return FausseReponse(200, json.dumps(corps), "application/json")

    faux_http.repondre_post = repondre
    expediteur = ExpediteurFichier(stockage)
    j2 = executer(parametres, http=faux_http, stockage=stockage, expediteur=expediteur,
                  redacteur=RedacteurIA(faux_http, parametres), maintenant=matin(2))
    assert j2["nb_nouveautes"] == 1 and j2["mode_redaction"] == "ia"
    assert len(j2["ecartes"]) == 1  # l'IA a écarté l'arrêté
    html = expediteur.envoyes[0]["html"]
    assert "Une réforme majeure de l&#x27;enregistrement est publiée." in html
    assert "Impact élevé" in html and "Six mois après publication" in html
