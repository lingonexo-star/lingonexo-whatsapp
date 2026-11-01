"""Sources ajoutées par l'administrateur."""

from datetime import date

import pytest

from veille import sources_admin
from veille.mode_github import ErreurAction, realiser
from veille.sources_admin import ErreurSourceAdmin
from veille.storage import StockageLocal

from test_web import PAGE, NOUVEAU, RSS

URL = "https://www.anpp.dz/fr/actualites"


@pytest.fixture
def st(parametres):
    return StockageLocal(parametres.dossier_donnees)


def test_ajout_d_une_page(parametres, st, faux_http):
    faux_http.ajouter(URL, PAGE.format(nouveau=""))
    source, nb = sources_admin.ajouter(parametres, st, faux_http, "ANPP – actualités", URL, "admin")
    assert source["type"] == "page" and nb == 3 and source["ajoutee_par"] == "admin"
    config = sources_admin.charger_configuration_complete(parametres, st)
    ajoutee = config.sources[-1]
    assert ajoutee.nom == "ANPP – actualités" and ajoutee.filtrer and ajoutee.options["ajoutee"]


def test_ajout_d_un_flux_rss_et_nom_par_defaut(parametres, st, faux_http):
    faux_http.ajouter("https://www.sante.gov.dz/feed/", RSS.format(nouveau=""), "application/rss+xml")
    source, nb = sources_admin.ajouter(parametres, st, faux_http, "", "www.sante.gov.dz/feed/")
    assert source["type"] == "rss" and source["nom"] == "sante.gov.dz" and source["url"] == "https://www.sante.gov.dz/feed/"


@pytest.mark.parametrize("adresse, message", [
    ("", "Indiquez l'adresse"),
    ("ftp://exemple.dz/x", "pas valide"),
    ("https://commerce.gov.dz/fr/", "déjà partie des sources"),
    ("https://introuvable.dz/page", "Impossible de lire cette adresse"),
])
def test_ajouts_refuses(parametres, st, faux_http, adresse, message):
    with pytest.raises(ErreurSourceAdmin, match=message):
        sources_admin.ajouter(parametres, st, faux_http, "x", adresse)
    assert sources_admin.lister(st) == []


def test_page_sans_publication_refusee(parametres, st, faux_http):
    faux_http.ajouter(URL, "<html><body><p>Bienvenue</p></body></html>")
    with pytest.raises(ErreurSourceAdmin, match="Aucune publication"):
        sources_admin.ajouter(parametres, st, faux_http, "x", URL)


def test_retrait(parametres, st, faux_http):
    faux_http.ajouter(URL, PAGE.format(nouveau=""))
    sources_admin.ajouter(parametres, st, faux_http, "ANPP", URL)
    with pytest.raises(ErreurSourceAdmin, match="sources de base"):
        sources_admin.retirer(st, parametres, "Presse (Google Actualités)")
    with pytest.raises(ErreurSourceAdmin, match="Aucune source ajoutée"):
        sources_admin.retirer(st, parametres, "https://autre.dz")
    assert sources_admin.retirer(st, parametres, "anpp.dz/fr/actualites/")["nom"] == "ANPP"
    assert sources_admin.lister(st) == []


def test_la_source_ajoutee_est_surveillee(parametres, st, faux_http, pdf_jo_vide):
    from test_runner import internet, lancer
    from veille.mailer import ExpediteurFichier
    internet(faux_http, pdf_jo_vide, parametres)
    faux_http.ajouter(URL, PAGE.format(nouveau=""))
    sources_admin.ajouter(parametres, st, faux_http, "ANPP", URL)
    boite = ExpediteurFichier(st)
    j1 = lancer(parametres, faux_http, st, boite, 1)
    assert next(s for s in j1["sources"] if s["nom"] == "ANPP")["statut"] == "initialisation"
    faux_http.ajouter(URL, PAGE.format(nouveau=NOUVEAU.replace("/fr/reglementation/arrete-prix", "/fr/decision-anpp")))
    j2 = lancer(parametres, faux_http, st, boite, 2)
    assert j2["statut"] == "NOUVEAUTES"
    assert any(el["source"] == "ANPP" for el in j2["elements"])


def test_actions_github(parametres, st, faux_http):
    faux_http.ajouter(URL, PAGE.format(nouveau=""))
    message = realiser(parametres, "Ajouter une source", nom="ANPP", adresse=URL, stockage=st, http=faux_http, par="amine-m")
    assert message.startswith("Source « ANPP » ajoutée (3 publications lues)")
    with pytest.raises(ErreurAction, match="déjà partie"):
        realiser(parametres, "Ajouter une source", nom="ANPP", adresse=URL, stockage=st, http=faux_http)
    assert "retirée" in realiser(parametres, "Retirer une source", adresse=URL, stockage=st)


def test_portail_ajout_et_retrait(parametres, faux_http):
    import re
    from test_portail import ADMIN, appel, se_connecter, Horloge
    from veille.mailer import ExpediteurFichier
    from veille.portail import Portail
    parametres.admins, parametres.secret, parametres.url_publique = [ADMIN], "s", "https://veille.exemple.net"
    stockage = StockageLocal(parametres.dossier_donnees)
    boite = ExpediteurFichier(stockage)
    portail = Portail(parametres, stockage=stockage, expediteur=boite, horloge=Horloge(), http=faux_http)
    cookie, _ = se_connecter(portail, boite)
    page = appel(portail, "GET", "/sources", cookie).corps
    jeton = re.search(r'name="jeton" value="([^"]+)"', page).group(1)
    rep = appel(portail, "POST", "/sources", cookie, jeton=jeton, nom="ANPP", adresse="https%3A%2F%2Fintrouvable.dz%2Fx")
    assert rep.statut == 400 and "Impossible de lire cette adresse" in rep.corps
    faux_http.ajouter(URL, PAGE.format(nouveau=""))
    rep = appel(portail, "POST", "/sources", cookie, jeton=jeton, nom="ANPP", adresse="https%3A%2F%2Fwww.anpp.dz%2Ffr%2Factualites")
    assert rep.entetes["Location"] == "/sources?msg=source_ajoutee"
    page = appel(portail, "GET", "/sources?msg=source_ajoutee", cookie).corps
    assert "Ajoutée depuis le portail" in page and "Source ajoutée" in page
    identifiant = sources_admin.lister(stockage)[0]["id"]
    rep = appel(portail, "POST", "/sources/retirer", cookie, jeton=jeton, id=identifiant)
    assert rep.entetes["Location"] == "/sources?msg=source_retiree" and sources_admin.lister(stockage) == []
