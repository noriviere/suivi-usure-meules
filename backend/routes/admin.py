"""Back-office : comptes et règles métier. Toutes les routes, sauf la connexion, exigent un compte connecté."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .. import config
from ..auth import utilisateurs
from ..auth.sessions import Limiteur
from ..auth.utilisateurs import ErreurUtilisateur
from ..services import reglages

router = APIRouter(prefix="/api/admin")
_limiteur = Limiteur(maxi=5, fenetre_s=300)


def utilisateur_courant(request: Request):
    utilisateur = utilisateurs.utilisateur_de_session(request.cookies.get(config.COOKIE_SESSION))
    if not utilisateur:
        raise HTTPException(status_code=401, detail="Connexion requise.")
    return utilisateur


def _erreur(erreur):
    return HTTPException(status_code=422, detail=str(erreur))


@router.get("/etat")
def etat():
    """Sans connexion : indique seulement s'il existe déjà un compte (pour afficher la bonne aide)."""
    reponse = {"aucun_compte": utilisateurs.nombre() == 0}
    if config.MODE_DEMO:
        reponse["compte_demo"] = {"nom": config.COMPTE_DEMO[0], "mot_de_passe": config.COMPTE_DEMO[1]}
    return reponse


@router.post("/connexion")
def connexion(donnees: dict, request: Request, reponse: Response):
    nom = str(donnees.get("nom") or "").strip()
    poste = request.client.host if request.client else "?"
    cles = (f"nom:{nom.lower()}", f"poste:{poste}")
    if any(_limiteur.bloque(cle) for cle in cles):
        raise HTTPException(status_code=429, detail="Trop d'essais. Réessayez dans quelques minutes.")
    utilisateur = utilisateurs.authentifier(nom, str(donnees.get("mot_de_passe") or ""))
    if not utilisateur:
        for cle in cles:
            _limiteur.echec(cle)
        raise HTTPException(status_code=401, detail="Nom d'utilisateur ou mot de passe incorrect.")
    for cle in cles:
        _limiteur.succes(cle)
    reponse.set_cookie(config.COOKIE_SESSION, utilisateurs.ouvrir_session(utilisateur), max_age=config.DUREE_SESSION_S,
                       httponly=True, samesite="strict", path="/")
    return {"id": utilisateur["id"], "nom": utilisateur["nom"]}


@router.post("/deconnexion")
def deconnexion(reponse: Response):
    reponse.delete_cookie(config.COOKIE_SESSION, path="/")
    return {"ok": True}


@router.get("/moi")
def moi(utilisateur=Depends(utilisateur_courant)):
    return utilisateur


# ---- section 1 : comptes -------------------------------------------------------
@router.get("/utilisateurs")
def liste_utilisateurs(utilisateur=Depends(utilisateur_courant)):
    return utilisateurs.lister()


@router.post("/utilisateurs")
def creer_utilisateur(donnees: dict, utilisateur=Depends(utilisateur_courant)):
    try:
        nouveau_id = utilisateurs.creer(donnees.get("nom"), str(donnees.get("mot_de_passe") or ""))
    except ErreurUtilisateur as erreur:
        raise _erreur(erreur)
    return {"id": nouveau_id}


@router.delete("/utilisateurs/{utilisateur_id}")
def supprimer_utilisateur(utilisateur_id: int, utilisateur=Depends(utilisateur_courant)):
    try:
        utilisateurs.supprimer(utilisateur_id, utilisateur["id"])
    except ErreurUtilisateur as erreur:
        raise _erreur(erreur)
    return {"ok": True}


@router.post("/utilisateurs/{utilisateur_id}/mot-de-passe")
def reinitialiser(utilisateur_id: int, donnees: dict, utilisateur=Depends(utilisateur_courant)):
    try:
        utilisateurs.reinitialiser_mot_de_passe(utilisateur_id, str(donnees.get("mot_de_passe") or ""))
    except ErreurUtilisateur as erreur:
        raise _erreur(erreur)
    return {"ok": True}


@router.post("/moi/nom")
def changer_nom(donnees: dict, utilisateur=Depends(utilisateur_courant)):
    try:
        utilisateurs.changer_mon_nom(utilisateur["id"], donnees.get("nom"), str(donnees.get("mot_de_passe") or ""))
    except ErreurUtilisateur as erreur:
        raise _erreur(erreur)
    return {"ok": True}


@router.post("/moi/mot-de-passe")
def changer_mot_de_passe(donnees: dict, reponse: Response, utilisateur=Depends(utilisateur_courant)):
    try:
        utilisateurs.changer_mon_mot_de_passe(utilisateur["id"], str(donnees.get("ancien") or ""), str(donnees.get("nouveau") or ""))
    except ErreurUtilisateur as erreur:
        raise _erreur(erreur)
    # le changement ferme les sessions ouvertes : on rouvre celle de cette personne
    nouveau = utilisateurs.authentifier(utilisateur["nom"], str(donnees.get("nouveau") or ""))
    if nouveau:
        reponse.set_cookie(config.COOKIE_SESSION, utilisateurs.ouvrir_session(nouveau), max_age=config.DUREE_SESSION_S,
                           httponly=True, samesite="strict", path="/")
    return {"ok": True}


# ---- section 2 : règles métier -----------------------------------------------
@router.get("/reglages")
def lire_reglages(utilisateur=Depends(utilisateur_courant)):
    return {**reglages.etat(), "historique": reglages.historique(30)}


@router.post("/reglages")
def modifier_reglages(donnees: dict, utilisateur=Depends(utilisateur_courant)):
    if donnees.get("reinitialiser"):
        reglages.reinitialiser(utilisateur["nom"])
    else:
        erreurs = reglages.enregistrer(donnees.get("regles"), utilisateur["nom"])
        if erreurs:
            raise HTTPException(status_code=422, detail=erreurs)
    return {**reglages.etat(), "historique": reglages.historique(30)}


# ---- section 3 : affichage de la page de saisie --------------------------------
@router.get("/affichage")
def lire_affichage(utilisateur=Depends(utilisateur_courant)):
    return reglages.affichage()


@router.post("/affichage")
def modifier_affichage(donnees: dict, utilisateur=Depends(utilisateur_courant)):
    reglages.definir_humour(donnees.get("humour"), utilisateur["nom"])
    return reglages.affichage()
