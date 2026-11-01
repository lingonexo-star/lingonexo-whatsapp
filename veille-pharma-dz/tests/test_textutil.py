from datetime import date

from veille.textutil import Filtre, couper, date_fr, date_longue_fr, extraire_date, normaliser


def test_normaliser_retire_accents_et_cesures():
    assert normaliser("produits pharma-\nceutiques à l’usage") == "produits pharmaceutiques a l'usage"
    assert normaliser("Médicament  Éssai") == "medicament essai"


def test_filtre_etoile_et_expressions():
    f = Filtre(["pharmac*", "dispositif* medica*", "ANPP"])
    assert f.correspondances("Industrie PHARMACEUTIQUE") == ["pharmac*"]
    assert f.correspondances("les dispositifs médicaux importés") == ["dispositif* medica*"]
    assert f.correspondances("décision de l'ANPP") == ["ANPP"]
    assert f.correspondances("anppx") == []
    assert f.compter("pharmacie et pharmacien") == 2


def test_dates():
    assert extraire_date("correspondant au 1er novembre 2026") == date(2026, 11, 1)
    assert extraire_date("le 31 février 2026 puis le 3 mars 2026") == date(2026, 3, 3)
    assert date_fr(date(2026, 11, 1)) == "1er novembre 2026"
    assert date_longue_fr(date(2026, 11, 2)) == "lundi 2 novembre 2026"


def test_couper():
    assert couper("Une phrase. Une autre phrase très longue", 16) == "Une phrase."
    assert couper("court", 20) == "court"
