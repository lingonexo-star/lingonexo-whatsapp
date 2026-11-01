"""Version gratuite (GitHub Actions + Gmail) : actions d'administration et tableau de bord."""

import json
from pathlib import Path

import pytest

from veille.annuaire import Annuaire
from veille.config import charger_parametres
from veille.mailer import ExpediteurFichier
from veille.mode_github import ErreurAction, principal, realiser, rendre_tableau_de_bord
from veille.storage import StockageLocal
from veille.summarize import RedacteurIA

from conftest import FausseReponse


@pytest.fixture
def p(tmp_path, parametres):
    parametres.admins = ["admin@exemple.dz"]
    return parametres


def test_actions_sur_les_destinataires(p):
    stockage = StockageLocal(p.dossier_donnees)
    boite = ExpediteurFichier(stockage)
    faire = lambda action, **k: realiser(p, action, stockage=stockage, expediteur=boite, par="amine-m", **k)  # noqa: E731

    assert "message de bienvenue" in faire("Ajouter un destinataire", email="Sara.Benali@labo.dz", nom="Sara Benali",
                                           fonction="Pharmacien responsable")
    assert boite.envoyes[-1]["destinataires"] == ["sara.benali@labo.dz"] and "Bienvenue" in boite.envoyes[-1]["sujet"]
    with pytest.raises(ErreurAction, match="figure déjà"):
        faire("Ajouter un destinataire", email="sara.benali@labo.dz")
    with pytest.raises(ErreurAction, match="pas valide"):
        faire("Ajouter un destinataire", email="pas-une-adresse")
    with pytest.raises(ErreurAction, match="Indiquez l'adresse"):
        faire("Retirer un destinataire")
    with pytest.raises(ErreurAction, match="ne figure pas"):
        faire("Retirer un destinataire", email="inconnu@labo.dz")

    annuaire = Annuaire(stockage, p)
    assert annuaire.trouver_par_email("sara.benali@labo.dz").ajoute_par == "amine-m"
    faire("Suspendre un destinataire", email="sara.benali@labo.dz")
    assert "sara.benali@labo.dz" not in annuaire.actifs()
    faire("Réactiver un destinataire", email="sara.benali@labo.dz")
    assert "sara.benali@labo.dz" in annuaire.actifs()
    assert "test envoyé" in faire("Envoyer un e-mail de test", email="sara.benali@labo.dz")
    assert boite.envoyes[-1]["sujet"].startswith("Message de test")
    faire("Retirer un destinataire", email="sara.benali@labo.dz")
    assert annuaire.trouver_par_email("sara.benali@labo.dz") is None
    assert faire("Ajouter un destinataire", email="k@labo.dz", bienvenue=False) == "k@labo.dz a été ajouté(e)."


def test_principal_ecrit_le_tableau_de_bord_et_le_resume(p, tmp_path):
    tableau, resume = tmp_path / "README.md", tmp_path / "resume.md"
    env = {"ACTION": "Ajouter un destinataire", "EMAIL": "nadia@labo.dz", "NOM": "Nadia Cherif", "BIENVENUE": "false",
           "GITHUB_ACTOR": "amine-m", "GITHUB_REPOSITORY": "moi/veille", "GITHUB_SERVER_URL": "https://github.com",
           "VEILLE_TABLEAU_DE_BORD": str(tableau), "GITHUB_STEP_SUMMARY": str(resume)}
    assert principal(p, env) == 0
    page = tableau.read_text()
    assert "# Veille réglementaire" in page and "| Nadia Cherif | nadia@labo.dz | — | Actif |" in page
    assert "https://github.com/moi/veille/actions/workflows/veille.yml" in page
    assert "Aucune vérification pour le moment" in page
    assert "Nadia Cherif a été ajouté(e)." in resume.read_text()
    # Erreur : code de retour 1 et message clair dans le résumé GitHub
    env.update({"ACTION": "Retirer un destinataire", "EMAIL": "personne@labo.dz"})
    assert principal(p, env) == 1
    assert "ne figure pas dans la liste" in resume.read_text()


def test_tableau_de_bord_apres_plusieurs_matins(p):
    entrees = [
        {"id": "2026-11-02T06-17-00", "date": "2026-11-02T06:17:00+01:00", "statut": "RAS", "nb_nouveautes": 0,
         "sources": [{"id": "joradp", "nom": "Journal officiel (JORADP)", "statut": "ok", "detail": "Aucun nouveau numéro."}],
         "elements": [], "email": {"envoye": False}},
        {"id": "2026-11-01T06-17-00", "date": "2026-11-01T06:17:00+01:00", "statut": "NOUVEAUTES", "nb_nouveautes": 1,
         "sources": [{"id": "joradp", "nom": "Journal officiel (JORADP)", "statut": "ok", "detail": "n° 58 analysé."}],
         "elements": [{"titre": "Enregistrement des médicaments", "url": "https://www.joradp.dz/x.pdf#page=2",
                       "source": "Journal officiel (JORADP)", "impact": "élevé"}],
         "rapport_md": "rapports/2026-11-01T06-17-00.md", "email": {"envoye": True, "destinataires": ["a@b.dz", "c@d.dz"]}},
    ]
    from datetime import datetime
    from veille.config import charger_configuration
    page = rendre_tableau_de_bord(entrees, [], charger_configuration(p.fichier_sources).sources, "../../actions",
                                  "suivi", datetime(2026, 11, 2, 8, 0))
    assert "| **Résultat** | **✅ RAS** |" in page
    assert "[Enregistrement des médicaments](https://www.joradp.dz/x.pdf#page=2)" in page
    assert "[note complète](suivi/rapports/2026-11-01T06-17-00.md)" in page
    assert "| 🔵 1 nouveauté | 1/1 | envoyé à 2 personnes |" in page


def test_ia_compatible_openai(p, faux_http):
    p.ia_url, p.ia_cle, p.ia_modele = "https://ia.exemple.com/v1/chat/completions", "cle-gratuite", "modele-mini"
    vus = []

    def repondre(url, options):
        vus.append((url, options["headers"]["Authorization"], options["json"]["model"]))
        contenu = "```json\n" + json.dumps({"chapeau": "Rien d'important."}) + "\n```"
        return FausseReponse(200, json.dumps({"choices": [{"message": {"content": contenu}}]}), "application/json")

    faux_http.repondre_post = repondre
    assert p.ia_active
    assert RedacteurIA(faux_http, p)._appeler("consigne", {}) == {"chapeau": "Rien d'important."}
    assert vus == [("https://ia.exemple.com/v1/chat/completions", "Bearer cle-gratuite", "modele-mini")]


def test_note_markdown_enregistree(parametres, faux_http, pdf_jo, pdf_jo_vide):
    from test_runner import internet, lancer, JO
    stockage = StockageLocal(parametres.dossier_donnees)
    internet(faux_http, pdf_jo_vide, parametres)
    lancer(parametres, faux_http, stockage, ExpediteurFichier(stockage), 1)
    faux_http.ajouter(JO.format(58), pdf_jo, "application/pdf")
    j2 = lancer(parametres, faux_http, stockage, ExpediteurFichier(stockage), 2)
    note = stockage.lire_texte(j2["rapport_md"])
    assert note.startswith("# Note de veille du lundi 2 novembre 2026")
    assert "[consulter](https://www.joradp.dz/FTP/jo-francais/2026/F2026058.pdf#page=2)" in note
