"""Portail : connexion par lien e-mail, rôles, gestion des destinataires."""

import re
from datetime import datetime, timedelta, timezone

import pytest

from veille.annuaire import Annuaire
from veille.config import charger_parametres
from veille.mailer import ExpediteurFichier
from veille.portail import Portail, Requete, construire_requete, prochaine_verification
from veille.securite import NOM_COOKIE
from veille.storage import StockageLocal

ADMIN = "admin@exemple.dz"


class Horloge:
    def __init__(self):
        self.t = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t


@pytest.fixture
def env(tmp_path, parametres):
    parametres.admins = [ADMIN]
    parametres.secret = "secret-de-test"
    parametres.url_publique = "https://veille.exemple.net"
    stockage = StockageLocal(parametres.dossier_donnees)
    boite = ExpediteurFichier(stockage)
    horloge = Horloge()
    lancements = []
    portail = Portail(parametres, stockage=stockage, expediteur=boite, horloge=horloge,
                      lanceur=lambda: lancements.append(1) or {})
    return portail, boite, horloge, lancements


def appel(portail, methode, chemin, cookie=None, **formulaire):
    url = "https://veille.exemple.net" + chemin
    corps = "&".join(f"{k}={v}" for k, v in formulaire.items()).encode() if formulaire else None
    return portail.traiter(construire_requete(methode, url, corps, f"{NOM_COOKIE}={cookie}" if cookie else None))


def se_connecter(portail, boite, email=ADMIN):
    rep = appel(portail, "POST", "/connexion", email=email)
    assert rep.statut == 200 and "Vérifiez votre messagerie" in rep.corps
    lien = re.search(r'href="https://veille\.exemple\.net/connexion/confirmer\?lien=([^"]+)"', boite.envoyes[-1]["html"]).group(1)
    page = appel(portail, "GET", f"/connexion/confirmer?lien={lien}")
    assert "Ouvrir ma session" in page.corps  # la simple ouverture du lien ne connecte pas
    rep = appel(portail, "POST", "/connexion/confirmer", lien=lien)
    assert rep.statut == 303
    cookie = rep.entetes["Set-Cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Lax" in cookie
    return cookie.split(";")[0].split("=", 1)[1], lien


def jeton(page):
    return re.search(r'name="jeton" value="([^"]+)"', page).group(1)


def test_sans_session_redirige_vers_connexion(env):
    portail, *_ = env
    rep = appel(portail, "GET", "/tableau-de-bord")
    assert rep.statut == 303 and rep.entetes["Location"] == "/connexion"
    assert rep.entetes["X-Frame-Options"] == "DENY" and "frame-ancestors 'none'" in rep.entetes["Content-Security-Policy"]


def test_connexion_administrateur(env):
    portail, boite, *_ = env
    cookie, lien = se_connecter(portail, boite)
    assert boite.envoyes[0]["destinataires"] == [ADMIN]
    assert appel(portail, "GET", "/", cookie).entetes["Location"] == "/tableau-de-bord"
    page = appel(portail, "GET", "/tableau-de-bord", cookie)
    assert page.statut == 200 and "Tableau de bord" in page.corps and "Administrateur" in page.corps
    # Le lien ne sert qu'une fois.
    assert appel(portail, "POST", "/connexion/confirmer", lien=lien).statut == 400


def test_adresse_inconnue_ne_recoit_rien_mais_meme_reponse(env):
    portail, boite, *_ = env
    rep = appel(portail, "POST", "/connexion", email="inconnu@ailleurs.com")
    assert rep.statut == 200 and "Vérifiez votre messagerie" in rep.corps
    assert boite.envoyes == []


def test_lien_expire(env):
    portail, boite, horloge, _ = env
    appel(portail, "POST", "/connexion", email=ADMIN)
    lien = re.search(r"lien=([^\"]+)\"", boite.envoyes[-1]["html"]).group(1)
    horloge.t += timedelta(minutes=16)
    assert "Lien expiré" in appel(portail, "GET", f"/connexion/confirmer?lien={lien}").corps
    assert appel(portail, "POST", "/connexion/confirmer", lien=lien).statut == 400


def test_session_expire_apres_12_heures(env):
    portail, boite, horloge, _ = env
    cookie, _ = se_connecter(portail, boite)
    horloge.t += timedelta(hours=12, minutes=1)
    assert appel(portail, "GET", "/tableau-de-bord", cookie).statut == 303


def test_cookie_falsifie_refuse(env):
    portail, boite, *_ = env
    cookie, _ = se_connecter(portail, boite)
    charge, signature = cookie.rsplit(".", 1)
    assert appel(portail, "GET", "/tableau-de-bord", f"{charge}.{'0' * len(signature)}").statut == 303


def test_limite_de_demandes(env):
    portail, boite, *_ = env
    for _ in range(7):
        appel(portail, "POST", "/connexion", email=ADMIN)
    assert len(boite.envoyes) == 5


def test_gestion_des_destinataires(env, parametres):
    portail, boite, *_ = env
    cookie, _ = se_connecter(portail, boite)
    page = appel(portail, "GET", "/destinataires", cookie).corps
    j = jeton(page)

    # Ajout avec message de bienvenue
    rep = appel(portail, "POST", "/destinataires", cookie, jeton=j, nom="Sara+Benali",
                email="Sara.Benali%40labo.dz", fonction="Pharmacien+responsable", bienvenue="1")
    assert rep.entetes["Location"] == "/destinataires?msg=ajoute_bienvenue"
    assert boite.envoyes[-1]["destinataires"] == ["sara.benali@labo.dz"]
    assert "Bienvenue" in boite.envoyes[-1]["sujet"]
    page = appel(portail, "GET", "/destinataires?msg=ajoute_bienvenue", cookie).corps
    assert "Sara Benali" in page and "sara.benali@labo.dz" in page and "Destinataire ajouté" in page

    # Doublon et adresse invalide refusés
    rep = appel(portail, "POST", "/destinataires", cookie, jeton=j, email="sara.benali%40labo.dz")
    assert rep.statut == 400 and "figure déjà" in rep.corps
    rep = appel(portail, "POST", "/destinataires", cookie, jeton=j, email="pas-une-adresse")
    assert rep.statut == 400 and "pas valide" in rep.corps

    annuaire = Annuaire(portail.stockage, parametres)
    sara = next(d for d in annuaire.lister() if d.email == "sara.benali@labo.dz")
    assert annuaire.actifs() == [ADMIN, "veille@exemple.dz", "sara.benali@labo.dz"]

    # Test, suspension, réactivation, retrait
    appel(portail, "POST", "/destinataires/action", cookie, jeton=j, id=sara.id, action="tester")
    assert boite.envoyes[-1]["sujet"].startswith("Message de test")
    appel(portail, "POST", "/destinataires/action", cookie, jeton=j, id=sara.id, action="suspendre")
    assert "sara.benali@labo.dz" not in annuaire.actifs()
    appel(portail, "POST", "/destinataires/action", cookie, jeton=j, id=sara.id, action="reactiver")
    assert "sara.benali@labo.dz" in annuaire.actifs()
    appel(portail, "POST", "/destinataires/action", cookie, jeton=j, id=sara.id, action="retirer")
    assert all(d.email != "sara.benali@labo.dz" for d in annuaire.lister())


def test_formulaire_sans_jeton_refuse(env, parametres):
    portail, boite, *_ = env
    cookie, _ = se_connecter(portail, boite)
    rep = appel(portail, "POST", "/destinataires", cookie, email="x%40y.dz")
    assert rep.entetes["Location"] == "/destinataires?msg=session"
    assert all(d.email != "x@y.dz" for d in Annuaire(portail.stockage, parametres).lister())


def test_destinataire_voit_le_journal_mais_pas_l_administration(env):
    portail, boite, *_ = env
    cookie, _ = se_connecter(portail, boite, "veille@exemple.dz")
    assert appel(portail, "GET", "/", cookie).entetes["Location"] == "/journal"
    journal = appel(portail, "GET", "/journal", cookie)
    assert journal.statut == 200 and "Journal des vérifications" in journal.corps
    assert "Destinataires" not in journal.corps.split("</nav>")[0].split("<nav")[1]
    assert appel(portail, "GET", "/destinataires", cookie).statut == 403


def test_retrait_coupe_l_acces_immediatement(env, parametres):
    portail, boite, *_ = env
    cookie_lecteur, _ = se_connecter(portail, boite, "veille@exemple.dz")
    annuaire = Annuaire(portail.stockage, parametres)
    cible = next(d for d in annuaire.lister() if d.email == "veille@exemple.dz")
    annuaire.changer_statut(cible.id, False)
    assert appel(portail, "GET", "/journal", cookie_lecteur).statut == 303


def test_verification_manuelle(env):
    portail, boite, _, lancements = env
    cookie, _ = se_connecter(portail, boite)
    j = jeton(appel(portail, "GET", "/tableau-de-bord", cookie).corps)
    rep = appel(portail, "POST", "/verification", cookie, jeton=j)
    assert rep.entetes["Location"] == "/tableau-de-bord?msg=verification" and lancements == [1]


def test_deconnexion(env):
    portail, boite, *_ = env
    cookie, _ = se_connecter(portail, boite)
    j = jeton(appel(portail, "GET", "/tableau-de-bord", cookie).corps)
    rep = appel(portail, "POST", "/deconnexion", cookie, jeton=j)
    assert rep.entetes["Location"] == "/connexion?msg=deconnecte" and "Max-Age=0" in rep.entetes["Set-Cookie"]


def test_sans_administrateur_configure(parametres):
    parametres.admins = []
    portail = Portail(parametres, stockage=StockageLocal(parametres.dossier_donnees))
    rep = portail.traiter(Requete("GET", "/connexion"))
    assert rep.statut == 503 and "VEILLE_ADMINS" in rep.corps


def test_prochaine_verification(parametres):
    avant = datetime(2026, 11, 2, 5, 0, tzinfo=timezone.utc)
    apres = datetime(2026, 11, 2, 6, 30, tzinfo=timezone.utc)
    assert prochaine_verification(parametres, avant).strftime("%d %H:%M") == "02 07:00"
    assert prochaine_verification(parametres, apres).strftime("%d %H:%M") == "03 07:00"


def test_parametres_admin():
    p = charger_parametres({"VEILLE_ADMINS": "Chef@Labo.dz", "VEILLE_URL_PUBLIQUE": "https://v.net/"})
    assert p.admins == ["chef@labo.dz"] and p.alerte_admin == ["chef@labo.dz"]
    assert p.url_journal == "https://v.net/journal"


def test_envoi_par_le_service_email_azure(parametres):
    from veille.mailer import ExpediteurAcs

    class FauxClient:
        def __init__(self):
            self.messages = []

        def begin_send(self, message):
            self.messages.append(message)

            class Attente:
                def result(self_inner):
                    return {"status": "Succeeded"}
            return Attente()

    parametres.acs_connexion = "endpoint=https://x.communication.azure.com/;accesskey=abc"
    parametres.acs_expediteur = "DoNotReply@abcd.azurecomm.net"
    client = FauxClient()
    ExpediteurAcs(parametres, client).envoyer(["a@x.dz", "b@y.dz"], "Sujet", "<p>Note</p>")
    # Un message par personne : aucun destinataire ne voit l'adresse des autres.
    assert [m["recipients"]["to"] for m in client.messages] == [[{"address": "a@x.dz"}], [{"address": "b@y.dz"}]]
    assert client.messages[0]["senderAddress"] == "DoNotReply@abcd.azurecomm.net"
    assert client.messages[0]["content"] == {"subject": "Sujet", "html": "<p>Note</p>"}


def test_mode_email_azure_par_defaut_dans_azure():
    p = charger_parametres({"WEBSITE_SITE_NAME": "veille", "ACS_CONNEXION": "endpoint=x", "AzureWebJobsStorage": "c"})
    assert p.mode_email == "acs"
