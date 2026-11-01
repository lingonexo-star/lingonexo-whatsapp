"""Azure Functions : la veille tourne seule dans le cloud Microsoft.

- veille_quotidienne : déclenchée par Azure chaque matin (paramètre VEILLE_PLANNING).
- portail            : site web d'administration (connexion par lien e-mail, destinataires,
                       journal, sources). Adresse : https://<nom-de-l-application>.azurewebsites.net/
"""

from __future__ import annotations

import logging

import azure.functions as func

from veille.config import charger_parametres
from veille.portail import Portail, construire_requete
from veille.runner import executer

app = func.FunctionApp()
_portail: Portail | None = None


@app.timer_trigger(schedule="%VEILLE_PLANNING%", arg_name="minuteur", run_on_startup=False, use_monitor=True)
def veille_quotidienne(minuteur: func.TimerRequest) -> None:
    entree = executer(charger_parametres(), declenchement="planifie")
    logging.info("Veille quotidienne : %s", entree["statut"])


@app.route(route="{*chemin}", methods=["GET", "POST"], auth_level=func.AuthLevel.ANONYMOUS)
def portail(req: func.HttpRequest) -> func.HttpResponse:
    global _portail
    if _portail is None:
        _portail = Portail(charger_parametres())
    requete = construire_requete(req.method, req.url, req.get_body(), req.headers.get("cookie"))
    reponse = _portail.traiter(requete)
    entetes = dict(reponse.entetes)
    type_contenu = entetes.pop("Content-Type", "text/plain; charset=utf-8").split(";")[0]
    return func.HttpResponse(reponse.corps, status_code=reponse.statut, headers=entetes,
                             mimetype=type_contenu, charset="utf-8")
