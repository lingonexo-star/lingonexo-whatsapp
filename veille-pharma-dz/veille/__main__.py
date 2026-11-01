"""Commandes de test et de diagnostic (à lancer depuis le dossier veille-pharma-dz).

    python -m veille lancer            # une vérification complète, comme chaque matin
    python -m veille journal           # affiche les dernières vérifications (RAS…)
    python -m veille sources           # teste l'accès à chaque source
    python -m veille jo 2026 57        # analyse un numéro précis du Journal officiel
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from .config import charger_configuration, charger_parametres
from .http import ClientHttp
from .runner import executer, lire_journal
from .sources import construire_source
from .sources.joradp import SourceJoradp
from .storage import ouvrir_stockage


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="python -m veille", description="Veille réglementaire pharma (Algérie)")
    commandes = parseur.add_subparsers(dest="commande", required=True)
    commandes.add_parser("lancer", help="lancer une vérification complète")
    commandes.add_parser("journal", help="afficher les dernières vérifications")
    commandes.add_parser("sources", help="tester l'accès à chaque source")
    jo = commandes.add_parser("jo", help="analyser un numéro du Journal officiel")
    jo.add_argument("annee", type=int)
    jo.add_argument("numero", type=int)
    args = parseur.parse_args(arguments)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.stdout.reconfigure(encoding="utf-8")
    parametres = charger_parametres()

    if args.commande == "lancer":
        entree = executer(parametres, declenchement="manuel")
        print(f"\nRésultat : {entree['statut']} ({entree['nb_nouveautes']} nouveauté(s))")
        for s in entree["sources"]:
            print(f"  [{s['statut']}] {s['nom']} – {s['detail']}")
        if entree["email"]["erreur"]:
            print(f"  E-mail : {entree['email']['erreur']}")
        return 0

    if args.commande == "journal":
        for entree in lire_journal(ouvrir_stockage(parametres), limite=20):
            print(f"{entree['date']}  {entree['statut']:<11} {entree['nb_nouveautes']} nouveauté(s)")
        return 0

    config = charger_configuration(parametres.fichier_sources)
    http = ClientHttp()

    if args.commande == "sources":
        for cfg in config.sources:
            if not cfg.actif:
                print(f"[désactivée] {cfg.nom}")
                continue
            source = construire_source(cfg, http, config)
            try:
                if isinstance(source, SourceJoradp):
                    dernier = source.trouver_dernier(date.today().year)
                    print(f"[OK]     {cfg.nom} – dernier numéro trouvé : {dernier}/{date.today().year}")
                else:
                    elements = source.lister()
                    print(f"[OK]     {cfg.nom} – {len(elements)} publications lues")
                    for el in elements[:5]:
                        print(f"           · {el.titre[:100]}")
            except Exception as exc:
                print(f"[ERREUR] {cfg.nom} – {exc}")
        return 0

    if args.commande == "jo":
        cfg = next(c for c in config.sources if c.type == "joradp")
        source = SourceJoradp(cfg, http, config)
        contenu = http.get_ok(source.url(args.annee, args.numero)).content
        trouvailles = source.analyser(args.annee, args.numero, contenu)
        print(f"{len(trouvailles)} texte(s) concernant le secteur :")
        for t in trouvailles:
            print(f"\n• {t.titre}\n  {t.reference} ({t.force})\n  {t.extrait[:300]}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
