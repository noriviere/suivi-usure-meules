"""Routes de la page de saisie (sans connexion : tous les postes de l'atelier)."""
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import config
from ..services.donnees import mediane
from ..services import travaux
from ..services.ecriture import FichierOccupe, ajouter_ligne
from ..services.journal import ecrire_chrono, ecrire_journal
from ..services.listes import charger, listes_deroulantes
from ..services.regles import perte_annuelle, traiter, vers_defaut, verifier_champ
from ..services.reglages import affichage as regles_affichage
from ..services.reglages import config as regles_en_vigueur

router = APIRouter()


@router.get("/api/etat")
def etat():
    return {"test": config.MODE_TEST, "demo": config.MODE_DEMO, "fichier": os.path.basename(config.FICHIER), "existe": os.path.exists(config.FICHIER)}


@router.get("/api/champs")
def champs():
    return regles_en_vigueur()


@router.get("/api/listes")
def listes():
    return listes_deroulantes()


@router.get("/api/formats")
def formats():
    return charger()["formats"]


@router.get("/api/meules")
def meules():
    return charger()["meules"]


@router.get("/api/mediane")
def api_mediane(article: str, machine: str, matiere: str):
    return mediane(article, machine, matiere)


@router.get("/api/perte")
def perte():
    return perte_annuelle()


@router.post("/api/habitude")
def habitude(donnees: dict):
    return {"message": verifier_champ(donnees.get("nom", ""), donnees.get("valeur"),
                                      donnees.get("article"), donnees.get("matiere"))}


@router.post("/api/verifier")
def verifier(donnees: dict):
    _, erreurs, avertissements = traiter(donnees)
    return {"erreurs": erreurs, "avertissements": avertissements}


@router.get("/api/affichage")
def affichage():
    return regles_affichage()


@router.post("/api/ajout")
def ajout(donnees: dict, request: Request):
    """Vérifie, puis lance l'enregistrement en tâche de fond (202 + identifiant). L'avancement et le
    résultat se lisent avec GET /api/ajout/{identifiant}."""
    t0 = time.perf_counter()
    propres, erreurs, avertissements = traiter(donnees)
    t_verif = time.perf_counter() - t0
    if erreurs:
        return JSONResponse(status_code=422, content={"erreurs": erreurs, "avertissements": avertissements})
    poste = request.client.host

    def travail(progression):
        mesures = {}
        try:
            defaut = vers_defaut(propres)
            ligne, calcules, info_defaut = ajouter_ligne(propres, defaut=defaut, progression=progression, mesures=mesures)
        except FichierOccupe as erreur:
            return 409, {"erreurs": [str(erreur)], "avertissements": avertissements}
        except Exception as erreur:
            return 500, {"erreurs": [f"Écriture impossible : {erreur}"], "avertissements": avertissements}
        notes = list(avertissements)
        if info_defaut:
            notes.append(f"Copiée dans l'onglet {info_defaut['onglet']} (ligne {info_defaut['ligne']})")
        try:
            ecrire_journal(poste, propres, ligne, notes)
        except OSError:                       # journal ouvert dans Excel : la ligne est déjà enregistrée, ne pas faire croire à un échec
            notes.append("Le journal des saisies n'a pas pu être écrit (fichier ouvert ailleurs).")
        mesures["verification"] = t_verif
        mesures["total_requete"] = time.perf_counter() - t0
        ecrire_chrono(mesures)
        return 200, {"ok": True, "ligne": ligne, "calcules": calcules,
                     "avertissements": avertissements, "defaut": info_defaut}

    return JSONResponse(status_code=202, content={"travail": travaux.lancer(travail)})


@router.get("/api/ajout/{identifiant}")
def suivi_ajout(identifiant: str):
    travail_lu = travaux.lire(identifiant)
    if travail_lu is None:
        return JSONResponse(status_code=404, content={"erreurs": ["Enregistrement inconnu (serveur redémarré ?). Vérifiez dans la consultation avant de recommencer."]})
    return {"etape": travail_lu["etape"], "fini": travail_lu["fini"], "statut": travail_lu["statut"], "corps": travail_lu["corps"]}
