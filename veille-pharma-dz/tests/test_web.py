from datetime import date

import pytest

from veille.config import charger_configuration
from veille.models import ErreurSource
from veille.sources import construire_source

PAGE = """<html><body><nav><a href="/fr/contact">Contact</a></nav>
<div class="actualites">
<a href="/fr/actualites/reunion-1">Le ministre reçoit une délégation d'investisseurs étrangers</a>
<a href="/fr/actualites/foire">Ouverture de la foire internationale d'Alger 2026</a>
<a href="/fr/actualites/bilan">Bilan des opérations de contrôle du mois de septembre</a>
{nouveau}
</div><a href="https://autre-site.dz/x">Un lien vers un autre site sans rapport aucun</a></body></html>"""

NOUVEAU = '<a href="/fr/reglementation/arrete-prix">Nouvel arrêté fixant les marges des produits pharmaceutiques</a>'

DETAIL = """<html><head><meta name="description" content="Publication d'un arrêté interministériel."></head>
<body><header>Menu</header><article><h1>Arrêté sur les marges</h1><p>Les marges applicables aux
médicaments importés sont plafonnées à 20 % à compter du 1er janvier 2027.</p></article></body></html>"""

RSS = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>MIPH</title>
<item><title>Le ministre inaugure une unité de production</title><link>https://www.miph.gov.dz/fr/a</link>
<description>Inauguration à Constantine.</description></item>
<item><title>Visite de travail à Oran</title><link>https://www.miph.gov.dz/fr/b</link></item>
{nouveau}</channel></rss>"""

RSS_NOUVEAU = """<item><title>Publication de l'arrêté relatif aux bonnes pratiques de distribution</title>
<link>https://www.miph.gov.dz/fr/c</link><pubDate>Mon, 02 Nov 2026 08:00:00 +0100</pubDate>
<description>&lt;p&gt;Le texte précise les obligations des distributeurs.&lt;/p&gt;</description></item>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Décret relatif aux médicaments génériques</title><link href="https://ex.dz/e1"/>
<updated>2026-11-02T08:00:00Z</updated><summary>Résumé</summary></entry></feed>"""


def _source(parametres, http, identifiant):
    config = charger_configuration(parametres.fichier_sources)
    cfg = next(c for c in config.sources if c.id == identifiant)
    return construire_source(cfg, http, config)


def test_page_premiere_fois_puis_nouveaute(parametres, faux_http):
    url = "https://www.commerce.gov.dz/fr"
    faux_http.ajouter(url, PAGE.format(nouveau=""))
    src = _source(parametres, faux_http, "commerce")

    premiere = src.executer(None, date(2026, 11, 1))
    assert premiere.statut == "initialisation"
    assert premiere.elements_verifies == 3  # liens trop courts et autres sites ignorés

    rien = src.executer(premiere.etat, date(2026, 11, 2))
    assert rien.statut == "ok" and rien.trouvailles == []

    faux_http.ajouter(url, PAGE.format(nouveau=NOUVEAU))
    faux_http.ajouter("https://www.commerce.gov.dz/fr/reglementation/arrete-prix", DETAIL)
    res = src.executer(rien.etat, date(2026, 11, 3))
    assert len(res.trouvailles) == 1
    t = res.trouvailles[0]
    assert t.url == "https://www.commerce.gov.dz/fr/reglementation/arrete-prix"
    assert "plafonnées à 20 %" in t.texte and "Menu" not in t.texte
    assert "1 concernant le secteur" in res.detail

    # Une nouveauté sans rapport avec la pharmacie n'est pas signalée.
    faux_http.ajouter(url, PAGE.format(nouveau=NOUVEAU + '<a href="/fr/x">Nouvel arrêté sur les prix du ciment importé</a>'))
    res2 = src.executer(res.etat, date(2026, 11, 4))
    assert res2.trouvailles == []


def test_page_vide_est_une_erreur(parametres, faux_http):
    faux_http.ajouter("https://www.commerce.gov.dz/fr", "<html><body>Accès refusé</body></html>")
    with pytest.raises(ErreurSource):
        _source(parametres, faux_http, "commerce").executer(None, date(2026, 11, 1))


def test_flux_rss_ne_garde_que_le_reglementaire(parametres, faux_http):
    url = "https://www.miph.gov.dz/fr/feed/"
    faux_http.ajouter(url, RSS.format(nouveau=""), "application/rss+xml")
    src = _source(parametres, faux_http, "miph")
    etat = src.executer(None, date(2026, 11, 1)).etat
    faux_http.ajouter(url, RSS.format(nouveau=RSS_NOUVEAU + "<item><title>Le ministre reçoit l'ambassadeur</title>"
                                                         "<link>https://www.miph.gov.dz/fr/d</link></item>"),
                      "application/rss+xml")
    res = src.executer(etat, date(2026, 11, 2))
    assert [t.titre for t in res.trouvailles] == [
        "Publication de l'arrêté relatif aux bonnes pratiques de distribution"]
    assert "obligations des distributeurs" in res.trouvailles[0].extrait


def test_flux_atom(parametres, faux_http):
    from veille.sources.web import SourceRss

    faux_http.ajouter("https://ex.dz/atom", ATOM, "application/atom+xml")
    src = _source(parametres, faux_http, "miph")
    src.cfg.url = "https://ex.dz/atom"
    elements = SourceRss.lister(src)
    assert elements[0].url == "https://ex.dz/e1"
    assert elements[0].titre == "Décret relatif aux médicaments génériques"


def test_google_news_construit_l_adresse(parametres):
    config = charger_configuration(parametres.fichier_sources)
    presse = next(c for c in config.sources if c.id == "presse")
    assert presse.url.startswith("https://news.google.com/rss/search?q=")
    assert presse.categorie == "presse" and presse.lire_page is False
