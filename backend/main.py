"""Point d'entrée : python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"""
import os
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, demo
from .routes import admin, consultation, saisie

demo.preparer()                      # mode démo (MEULES_DEMO=1) : fausses données ; sans effet sinon
app = FastAPI(title="Suivi d'usure des meules")
app.mount("/static", StaticFiles(directory=os.path.join(config.DOSSIER_FRONTEND)), name="static")
app.include_router(saisie.router)
app.include_router(consultation.router)
app.include_router(admin.router)

# --- Arrêt automatique quand le serveur a été lancé « le temps d'une consultation » ---
# (scripts\serveur_temporaire.bat règle ARRET_INACTIF_MIN ; sur le PC serveur, la variable est absente : jamais d'arrêt)
_derniere_requete = time.time()


@app.middleware("http")
async def suivre_activite(request: Request, call_next):
    global _derniere_requete
    _derniere_requete = time.time()
    return await call_next(request)


def _surveiller_inactivite(minutes):
    while True:
        time.sleep(30)
        if time.time() - _derniere_requete > minutes * 60:
            os._exit(0)


if os.environ.get("ARRET_INACTIF_MIN"):
    threading.Thread(target=_surveiller_inactivite, args=(float(os.environ["ARRET_INACTIF_MIN"]),), daemon=True).start()


def _page(nom):
    return FileResponse(os.path.join(config.DOSSIER_FRONTEND, "html", nom))


@app.get("/")
def accueil():
    return _page("index.html")


@app.get("/formulaire")
def formulaire():
    return _page("index.html")


@app.get("/consultation")
def page_consultation():
    return _page("consultation.html")


@app.get("/admin")
def page_admin():
    return _page("admin.html")


@app.get("/sante")
def sante():
    return {"ok": True}
