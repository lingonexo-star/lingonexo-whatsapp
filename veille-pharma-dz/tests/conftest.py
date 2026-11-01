"""Outils de test : faux Internet (pages, flux, PDF du Journal officiel)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from requests.structures import CaseInsensitiveDict

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from veille.config import charger_parametres  # noqa: E402
from veille.models import ErreurSource  # noqa: E402


def fabriquer_pdf(pages: list[str]) -> bytes:
    """Petit PDF texte (police Helvetica, encodage WinAnsi pour les accents)."""

    def chaine(ligne: str) -> bytes:
        brut = ligne.encode("cp1252")
        return b"(" + brut.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"

    objets: list[bytes] = []
    nb_pages = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(nb_pages))
    objets.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objets.append(f"<< /Type /Pages /Kids [{kids}] /Count {nb_pages} >>".encode())
    objets.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, texte in enumerate(pages):
        flux = b"BT /F1 9 Tf 11 TL 30 810 Td " + b" ".join(
            chaine(l) + b" Tj T*" for l in texte.splitlines()) + b" ET"
        objets.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {5 + 2 * i} 0 R >>".encode())
        objets.append(b"<< /Length " + str(len(flux)).encode() + b" >>\nstream\n" + flux + b"\nendstream")

    sortie = bytearray(b"%PDF-1.4\n")
    positions = []
    for n, obj in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    for p in positions:
        sortie += f"{p:010d} 00000 n \n".encode()
    sortie += f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(sortie)


class FausseReponse:
    def __init__(self, status=200, contenu=b"", type_contenu="text/html; charset=utf-8", url=""):
        self.status_code = status
        self.content = contenu if isinstance(contenu, bytes) else contenu.encode("utf-8")
        self.headers = CaseInsensitiveDict({"content-type": type_contenu})
        self.url = url

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        return json.loads(self.content)

    def iter_content(self, chunk_size=1):
        yield self.content[:chunk_size]

    def close(self):
        pass


class FauxHttp:
    """Remplace ClientHttp : chaque URL renvoie ce qu'on a déclaré dans `pages`."""

    def __init__(self):
        self.pages: dict[str, FausseReponse] = {}
        self.en_panne: set[str] = set()
        self.posts: list[dict] = []
        self.repondre_post = None

    def ajouter(self, url, contenu, type_contenu="text/html; charset=utf-8", status=200):
        self.pages[url] = FausseReponse(status, contenu, type_contenu, url)

    def get(self, url, **_):
        if any(url.startswith(p) for p in self.en_panne):
            raise ErreurSource(f"Site injoignable : {url} (ConnectionError)")
        return self.pages.get(url.split("#")[0], FausseReponse(404, b"Not found", url=url))

    def get_ok(self, url, **options):
        reponse = self.get(url, **options)
        if reponse.status_code != 200:
            raise ErreurSource(f"Réponse HTTP {reponse.status_code} pour {url}")
        return reponse

    def est_pdf(self, url, codes_absents=(404, 410)):
        reponse = self.get(url)
        if reponse.status_code in codes_absents:
            return False
        if reponse.status_code != 200:
            raise ErreurSource(f"Réponse HTTP inattendue {reponse.status_code} pour {url}")
        return reponse.content.startswith(b"%PDF")

    def post(self, url, **options):
        self.posts.append({"url": url, **options})
        return self.repondre_post(url, options)


@pytest.fixture
def faux_http():
    return FauxHttp()


@pytest.fixture
def parametres(tmp_path):
    sources = tmp_path / "sources.yaml"
    sources.write_text((RACINE / "sources.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return charger_parametres({
        "VEILLE_DESTINATAIRES": "veille@exemple.dz",
        "VEILLE_ALERTE_ADMIN": "it@exemple.dz",
        "VEILLE_MODE_EMAIL": "fichier",
        "VEILLE_STOCKAGE": "local",
        "VEILLE_DOSSIER_DONNEES": str(tmp_path / "donnees"),
        "VEILLE_SOURCES": str(sources),
    })


# Un numéro réaliste du Journal officiel : sommaire + corps, avec un texte
# pharmaceutique, un texte sans rapport (qui cite la loi sanitaire dans ses
# visas) et une nomination (exclue).
JO_PAGE_1 = """JOURNAL OFFICIEL DE LA REPUBLIQUE ALGERIENNE N° 58
Mercredi 13 Joumada El Oula 1448
Correspondant au 21 octobre 2026
SOMMAIRE
DÉCRETS
Décret exécutif n° 26-311 du 10 Joumada El Oula 1448 correspondant au 18 octobre 2026 fixant
les modalités d'enregistrement des produits pharmaceutiques à usage humain ........ 3
Décret exécutif n° 26-312 du 10 Joumada El Oula 1448 correspondant au 18 octobre 2026 fixant
les conditions d'exploitation des carrières ........ 5
ARRÊTÉS, DÉCISIONS ET AVIS
MINISTÈRE DE L'INDUSTRIE
PHARMACEUTIQUE
Arrêté du 5 Joumada El Oula 1448 correspondant au 13 octobre 2026 fixant la liste des
documents du dossier d'agrément ........ 6"""

JO_PAGE_2 = """DÉCRETS
Décret exécutif n° 26-311 du 10 Joumada El Oula 1448 correspondant au 18 octobre 2026 fixant
les modalités d'enregistrement des produits pharma-
ceutiques à usage humain.
————
Le Premier ministre,
Sur le rapport du ministre de l'industrie pharmaceutique,
Vu la loi n° 18-11 du 2 juillet 2018 relative à la santé ;
Décrète :
Article 1er. — Le présent décret a pour objet de fixer les modalités d'enregistrement des
produits pharmaceutiques à usage humain auprès de l'agence nationale des produits pharmaceutiques.
Art. 2. — La demande d'enregistrement est déposée par voie électronique.
Art. 3. — Le présent décret entre en vigueur six mois après sa publication.
Décret exécutif n° 26-312 du 10 Joumada El Oula 1448 correspondant au 18 octobre 2026 fixant
les conditions d'exploitation des carrières.
————
Le Premier ministre,
Vu la loi n° 18-11 du 2 juillet 2018 relative à la santé, notamment ses dispositions sur les
produits pharmaceutiques et les médicaments ;
Vu l'avis de l'agence nationale des produits pharmaceutiques ;
Décrète :
Article 1er. — Le présent décret fixe les conditions d'exploitation des carrières de granulats."""

JO_PAGE_3 = """Décret présidentiel du 12 octobre 2026 portant nomination du directeur général de
l'agence nationale des produits pharmaceutiques.
————
Par décret présidentiel du 12 octobre 2026, M. X est nommé directeur général.
ARRÊTÉS, DÉCISIONS ET AVIS
MINISTÈRE DE L'INDUSTRIE
PHARMACEUTIQUE
Arrêté du 5 Joumada El Oula 1448 correspondant au 13 octobre 2026 fixant la liste des
documents du dossier d'agrément.
————
Le ministre de l'industrie pharmaceutique,
Vu le décret exécutif n° 21-82 du 23 février 2021 ;
Arrête :
Article 1er. — Le présent arrêté a pour objet de fixer la liste des documents constituant le
dossier de demande d'agrément des établissements.
Art. 2. — Le dossier est déposé auprès des services du ministère."""


@pytest.fixture
def pdf_jo():
    return fabriquer_pdf([JO_PAGE_1, JO_PAGE_2, JO_PAGE_3])


@pytest.fixture
def pdf_jo_vide():
    return fabriquer_pdf(["""JOURNAL OFFICIEL DE LA REPUBLIQUE ALGERIENNE N° 59
Correspondant au 25 octobre 2026
DÉCRETS
Décret exécutif n° 26-320 du 22 octobre 2026 fixant les conditions de la pêche artisanale.
————
Le Premier ministre,
Article 1er. — Le présent décret fixe les conditions de la pêche artisanale en mer."""])
