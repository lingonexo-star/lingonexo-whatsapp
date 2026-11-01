"""Azure Functions : la veille tourne seule dans le cloud Microsoft.

- veille_quotidienne : déclenchée par Azure chaque matin (paramètre VEILLE_PLANNING).
- journal            : page web listant chaque vérification (RAS, nouveautés, erreurs).
- rapport            : article complet d'un jour donné.
- lancer             : bouton « Lancer une vérification maintenant » du journal.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

import azure.functions as func

from veille.config import charger_parametres
from veille.render import rendre_journal
from veille.runner import executer, lire_journal
from veille.storage import ouvrir_stockage

app = func.FunctionApp()
_RX_ID = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$")


def _html(contenu: str, statut: int = 200) -> func.HttpResponse:
    return func.HttpResponse(contenu, status_code=statut, mimetype="text/html", charset="utf-8")


@app.timer_trigger(schedule="%VEILLE_PLANNING%", arg_name="minuteur", run_on_startup=False, use_monitor=True)
def veille_quotidienne(minuteur: func.TimerRequest) -> None:
    entree = executer(charger_parametres(), declenchement="planifie")
    logging.info("Veille quotidienne : %s", entree["statut"])


@app.route(route="journal", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def journal(req: func.HttpRequest) -> func.HttpResponse:
    stockage = ouvrir_stockage(charger_parametres())
    return _html(rendre_journal(lire_journal(stockage), code=req.params.get("code", "")))


@app.route(route="rapport", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def rapport(req: func.HttpRequest) -> func.HttpResponse:
    identifiant = req.params.get("id", "")
    if not _RX_ID.match(identifiant):
        return _html("<p>Identifiant invalide.</p>", 400)
    contenu = ouvrir_stockage(charger_parametres()).lire_texte(f"rapports/{identifiant}.html")
    return _html(contenu) if contenu else _html("<p>Rapport introuvable.</p>", 404)


@app.route(route="lancer", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def lancer(req: func.HttpRequest) -> func.HttpResponse:
    executer(charger_parametres(), declenchement="manuel")
    code = req.params.get("code", "")
    destination = "journal" + (f"?code={quote(code)}" if code else "")
    return func.HttpResponse(status_code=303, headers={"Location": destination})
