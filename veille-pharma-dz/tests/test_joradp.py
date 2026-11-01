from datetime import date

import pytest

from veille.config import charger_configuration
from veille.models import ErreurSource
from veille.sources.joradp import (
    SourceJoradp, analyser_titre, decouper, dedoublonner, extraire_pages,
)

from conftest import JO_PAGE_1, JO_PAGE_2, JO_PAGE_3

URL = "https://www.joradp.dz/FTP/jo-francais/2026/F2026{:03d}.pdf"


def source(parametres, http):
    config = charger_configuration(parametres.fichier_sources)
    cfg = next(c for c in config.sources if c.id == "joradp")
    return SourceJoradp(cfg, http, config)


def test_pdf_lisible(pdf_jo):
    pages = extraire_pages(pdf_jo)
    assert len(pages) == 3
    assert "Décret exécutif n° 26-311" in pages[1]
    assert "MINISTÈRE DE L'INDUSTRIE" in pages[2]


def test_decoupage_et_doublons_du_sommaire():
    segments = dedoublonner(decouper([JO_PAGE_1, JO_PAGE_2, JO_PAGE_3]))
    titres = [s.titre for s in segments]
    assert len(segments) == 4, titres
    enregistrement = next(s for s in segments if "26-311" in s.titre)
    assert not enregistrement.sommaire  # la version du corps est retenue
    assert enregistrement.titre.endswith("produits pharmaceutiques à usage humain")
    assert enregistrement.page == 2
    arrete = next(s for s in segments if s.type_texte == "Arrêté")
    assert arrete.autorite == "MINISTÈRE DE L'INDUSTRIE PHARMACEUTIQUE"
    assert "Article 1er" in arrete.corps


def test_analyse_titre():
    infos = analyser_titre("Décret exécutif n° 26-311 du 10 Joumada El Oula 1448 correspondant au "
                           "18 octobre 2026 fixant les modalités d'enregistrement")
    assert infos == {"numero": "26-311", "date_texte": "18 octobre 2026",
                     "objet": "fixant les modalités d'enregistrement"}


def test_selection_des_textes_pharmaceutiques(parametres, faux_http, pdf_jo):
    trouvailles = source(parametres, faux_http).analyser(2026, 58, pdf_jo)
    titres = [t.titre for t in trouvailles]
    # Retenus : le décret d'enregistrement (titre) et l'arrêté du ministère (autorité).
    # Écartés : les carrières (pharma seulement dans les visas) et la nomination (exclusion).
    assert len(trouvailles) == 2, titres
    decret = next(t for t in trouvailles if t.type_texte == "Décret exécutif")
    assert decret.reference == "Journal officiel n° 58 du 21 octobre 2026 – page 2 du PDF"
    assert decret.url == URL.format(58) + "#page=2"
    assert decret.extrait.startswith("Le présent décret a pour objet de fixer les modalités")
    assert decret.force == "forte"
    arrete = next(t for t in trouvailles if t.type_texte == "Arrêté")
    assert arrete.autorite == "Ministère de l'industrie pharmaceutique"


def test_premiere_execution_initialise(parametres, faux_http, pdf_jo):
    for n in range(1, 58):
        faux_http.ajouter(URL.format(n), pdf_jo, "application/pdf")
    res = source(parametres, faux_http).executer(None, date(2026, 11, 1))
    assert res.statut == "initialisation"
    assert res.etat == {"annee": 2026, "dernier_numero": 57}
    assert "n° 57/2026" in res.detail
    assert res.trouvailles == []


def test_nouveau_numero_detecte(parametres, faux_http, pdf_jo, pdf_jo_vide):
    faux_http.ajouter(URL.format(57), pdf_jo_vide, "application/pdf")
    faux_http.ajouter(URL.format(58), pdf_jo, "application/pdf")
    faux_http.ajouter(URL.format(59), pdf_jo_vide, "application/pdf")
    res = source(parametres, faux_http).executer({"annee": 2026, "dernier_numero": 57}, date(2026, 11, 1))
    assert res.statut == "ok"
    assert res.etat == {"annee": 2026, "dernier_numero": 59}
    assert len(res.trouvailles) == 2
    assert "58/2026, 59/2026" in res.detail


def test_aucun_nouveau_numero(parametres, faux_http, pdf_jo):
    faux_http.ajouter(URL.format(57), pdf_jo, "application/pdf")
    res = source(parametres, faux_http).executer({"annee": 2026, "dernier_numero": 57}, date(2026, 11, 1))
    assert res.statut == "ok" and res.trouvailles == []
    assert res.detail == "Aucun nouveau numéro depuis le n° 57/2026."


def test_site_bloque_ne_donne_jamais_ras(parametres, faux_http):
    # Le dernier numéro connu n'est plus accessible : c'est une erreur, pas « rien de nouveau ».
    with pytest.raises(ErreurSource):
        source(parametres, faux_http).executer({"annee": 2026, "dernier_numero": 57}, date(2026, 11, 1))
    faux_http.en_panne.add("https://www.joradp.dz")
    with pytest.raises(ErreurSource):
        source(parametres, faux_http).executer(None, date(2026, 11, 1))


def test_changement_d_annee(parametres, faux_http, pdf_jo, pdf_jo_vide):
    faux_http.ajouter("https://www.joradp.dz/FTP/jo-francais/2026/F2026090.pdf", pdf_jo_vide, "application/pdf")
    faux_http.ajouter("https://www.joradp.dz/FTP/jo-francais/2027/F2027001.pdf", pdf_jo, "application/pdf")
    res = source(parametres, faux_http).executer({"annee": 2026, "dernier_numero": 90}, date(2027, 1, 3))
    assert res.etat == {"annee": 2027, "dernier_numero": 1}
    assert len(res.trouvailles) == 2


def test_pdf_illisible_signale_pour_lecture_humaine(parametres, faux_http, pdf_jo):
    faux_http.ajouter(URL.format(57), pdf_jo, "application/pdf")
    faux_http.ajouter(URL.format(58), b"%PDF-1.4 corrompu", "application/pdf")
    res = source(parametres, faux_http).executer({"annee": 2026, "dernier_numero": 57}, date(2026, 11, 1))
    assert res.etat["dernier_numero"] == 58
    assert len(res.trouvailles) == 1 and res.trouvailles[0].a_verifier
    assert "illisible" in res.detail
