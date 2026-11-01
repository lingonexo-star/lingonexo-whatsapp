"""Administration par e-mail (version gratuite) : commandes, sécurité, lecture de la boîte."""

from email.message import EmailMessage

import pytest

from veille import sources_admin
from veille.annuaire import Annuaire
from veille.courrier import authentifie, identifier, lignes_utiles, relever, traiter
from veille.mailer import ExpediteurFichier
from veille.storage import StockageLocal

from test_web import PAGE

ADMIN = "amine@labo-exemple.com"
AUTH_OK = ("mx.google.com; dkim=pass header.i=@labo-exemple.com header.s=s1; spf=pass (google.com: domain of "
           "amine@labo-exemple.com designates 1.2.3.4 as permitted sender) smtp.mailfrom=amine@labo-exemple.com; "
           "dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=labo-exemple.com")


def message(sujet, corps, expediteur=ADMIN, auth=AUTH_OK):
    m = EmailMessage()
    m["From"] = f"Amine <{expediteur}>"
    m["To"] = "veille@gmail.com"
    m["Subject"] = sujet
    if auth:
        m["Authentication-Results"] = auth
    m.set_content(corps)
    return m


@pytest.fixture
def env(parametres):
    parametres.admins = [ADMIN]
    stockage = StockageLocal(parametres.dossier_donnees)
    return parametres, stockage, ExpediteurFichier(stockage)


@pytest.mark.parametrize("sujet, attendu", [
    ("Ajouter", ("ajouter", "")),
    ("RE: Tr: ajouter sara@x.dz", ("ajouter", "sara@x.dz")),
    ("ÉTAT", ("etat", "")),
    ("Retirer source https://www.anpp.dz", ("retirer_source", "https://www.anpp.dz")),
    ("Source : https://www.anpp.dz", ("source", "https://www.anpp.dz")),
    ("Réactiver", ("reactiver", "")),
    ("Vérifier", ("verifier", "")),
    ("Bonjour", ("inconnue", "Bonjour")),
])
def test_identifier_la_commande(sujet, attendu):
    assert identifier(sujet) == attendu


def test_signature_et_message_cite_ignores():
    corps = ("Bonjour,\nsara@x.dz, Sara\n\nCordialement,\nAmine\namine@labo-exemple.com\n"
             "Le lun. 2 nov. 2026, Veille a écrit :\n> ancien message")
    assert lignes_utiles(corps) == ["Bonjour,", "sara@x.dz, Sara"]


def test_authentification():
    assert authentifie(message("x", "y"), ADMIN)
    assert not authentifie(message("x", "y", auth=None), ADMIN)
    faux = "mx.google.com; dkim=pass header.i=@pirate.com; spf=pass smtp.mailfrom=x@pirate.com; dmarc=pass header.from=pirate.com"
    assert not authentifie(message("x", "y", auth=faux), ADMIN)


def test_ajouter_plusieurs_personnes(env):
    p, st, boite = env
    corps = ("Bonjour, merci d'ajouter :\nsara.benali@labo.dz, Sara Benali, Pharmacien responsable\n"
             "karim@labo.dz ; Karim Haddad\npas-une-adresse\n\nCordialement\nAmine Mohamed — amine@labo-exemple.com")
    assert traiter(p, message("Ajouter", corps), st, boite)
    annuaire = Annuaire(st, p)
    sara = annuaire.trouver_par_email("sara.benali@labo.dz")
    assert sara.nom == "Sara Benali" and sara.fonction == "Pharmacien responsable" and sara.ajoute_par == ADMIN
    assert annuaire.trouver_par_email("karim@labo.dz").nom == "Karim Haddad"
    reponse = boite.envoyes[-1]
    assert reponse["destinataires"] == [ADMIN] and reponse["sujet"] == "Re: Ajouter"
    assert reponse["html"].count("✓") == 2 and "Sara Benali a été ajouté(e)" in reponse["html"]
    assert sum(1 for e in boite.envoyes if "Bienvenue" in e["sujet"]) == 2


def test_retirer_suspendre_test(env):
    p, st, boite = env
    Annuaire(st, p).ajouter("sara@labo.dz", "Sara")
    traiter(p, message("Suspendre", "sara@labo.dz"), st, boite)
    assert "sara@labo.dz" not in Annuaire(st, p).actifs()
    traiter(p, message("Réactiver", "sara@labo.dz"), st, boite)
    traiter(p, message("Test", "sara@labo.dz"), st, boite)
    assert any(e["sujet"].startswith("Message de test") and e["destinataires"] == ["sara@labo.dz"] for e in boite.envoyes)
    traiter(p, message("Retirer", "sara@labo.dz\ninconnu@labo.dz"), st, boite)
    html = boite.envoyes[-1]["html"]
    assert "✓ Sara a été retiré(e)" in html and "✗ inconnu@labo.dz" in html


def test_ajouter_une_source(env, faux_http):
    p, st, boite = env
    faux_http.ajouter("https://www.anpp.dz/actualites", PAGE.format(nouveau=""))
    traiter(p, message("Source", "https://www.anpp.dz/actualites, ANPP"), st, boite, http=faux_http)
    assert sources_admin.lister(st)[0]["nom"] == "ANPP"
    assert "Source « ANPP » ajoutée" in boite.envoyes[-1]["html"]


def test_etat_liste_aide_et_commande_inconnue(env):
    p, st, boite = env
    traiter(p, message("État", ""), st, boite)
    assert "Aucune vérification" in boite.envoyes[-1]["html"]
    st.ecrire_json("journal/2026-11-02T06-21-00.json", {
        "id": "2026-11-02T06-21-00", "date": "2026-11-02T06:21:00+01:00", "statut": "RAS", "nb_nouveautes": 0,
        "sources": [{"id": "joradp", "nom": "Journal officiel (JORADP)", "statut": "ok", "detail": "Aucun nouveau numéro."}],
        "elements": [], "email": {}})
    traiter(p, message("État", ""), st, boite)
    html = boite.envoyes[-1]["html"]
    assert "RAS" in html and "lundi 2 novembre 2026 à 06:21" in html
    traiter(p, message("Liste", ""), st, boite)
    assert "Sources surveillées" in boite.envoyes[-1]["html"]
    traiter(p, message("Bonjour Amine", "une question"), st, boite)
    assert "pas reconnu la commande" in boite.envoyes[-1]["html"]


def test_verification_a_la_demande(env):
    p, st, boite = env
    traiter(p, message("Vérifier", ""), st, boite, lanceur=lambda: {
        "statut": "RAS", "nb_nouveautes": 0, "email": {}})
    assert "RAS : toutes les sources ont été vérifiées" in boite.envoyes[-1]["html"]


def test_messages_ignores(env):
    p, st, boite = env
    assert not traiter(p, message("Ajouter", "x@y.dz", expediteur="inconnu@ailleurs.com"), st, boite)
    assert not traiter(p, message("Ajouter", "x@y.dz", auth=None), st, boite)
    assert boite.envoyes == [] and Annuaire(st, p).trouver_par_email("x@y.dz") is None


class FausseBoite:
    def __init__(self, messages):
        self.messages = messages  # numéro -> (expéditeur, message)
        self.lus, self.recherches = set(), []

    def login(self, *a):
        pass

    def select(self, *a):
        return "OK", [b"1"]

    def search(self, _charset, *critere):
        self.recherches.append(critere)
        adresse = critere[-1].strip('"')
        trouves = [n for n, (exp, _) in self.messages.items() if exp == adresse and n not in self.lus]
        return "OK", [b" ".join(trouves)]

    def fetch(self, numero, _parts):
        return "OK", [(b"", self.messages[numero][1].as_bytes())]

    def store(self, numero, *_):
        self.lus.add(numero)

    def logout(self):
        pass


def test_releve_de_la_boite(env):
    p, st, boite = env
    imap = FausseBoite({b"1": (ADMIN, message("Ajouter", "sara@labo.dz, Sara")),
                        b"2": ("ami@gmail.com", message("Ajouter", "x@y.dz", expediteur="ami@gmail.com")),
                        b"3": (ADMIN, message("Aide", ""))})
    assert relever(p, st, boite, imap_fabrique=lambda: imap) == 2
    assert imap.lus == {b"1", b"3"}  # les messages des autres personnes ne sont ni lus ni marqués
    assert all(c[0] == "UNSEEN" and c[1] == "FROM" for c in imap.recherches)
    assert relever(p, st, boite, imap_fabrique=lambda: imap) == 0


def test_les_messages_de_la_veille_ne_sont_pas_des_commandes(env):
    p, st, boite = env
    note = message("Veille réglementaire pharma – 2 nouveautés", "...")
    note["X-Veille-Reglementaire"] = "1"
    imap = FausseBoite({b"1": (ADMIN, note)})
    assert relever(p, st, boite, imap_fabrique=lambda: imap) == 0
    assert imap.lus == set() and boite.envoyes == []
