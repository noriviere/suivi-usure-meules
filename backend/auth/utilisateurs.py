"""Comptes du back-office (un seul type de compte : tous les comptes ont les mêmes droits)."""
import datetime
import re

from . import db, mots_de_passe, sessions
from .. import config


class ErreurUtilisateur(ValueError):
    """Erreur à afficher telle quelle à la personne (message en français)."""


MOTIF_NOM = re.compile(r"^[A-Za-z0-9._-]{3,32}$")


def _maintenant():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _verifier_nom(nom):
    nom = (nom or "").strip()
    if not MOTIF_NOM.match(nom):
        raise ErreurUtilisateur("Nom d'utilisateur : 3 à 32 caractères (lettres, chiffres, point, tiret, tiret bas).")
    return nom


def _public(ligne):
    return {"id": ligne["id"], "nom": ligne["nom"], "cree_le": ligne["cree_le"],
            "derniere_connexion": ligne["derniere_connexion"]}


def nombre():
    with db.connexion() as con:
        return con.execute("SELECT COUNT(*) FROM utilisateurs").fetchone()[0]


def lister():
    with db.connexion() as con:
        return [_public(ligne) for ligne in con.execute("SELECT * FROM utilisateurs ORDER BY nom COLLATE NOCASE")]


def trouver(utilisateur_id):
    with db.connexion() as con:
        ligne = con.execute("SELECT * FROM utilisateurs WHERE id = ?", (utilisateur_id,)).fetchone()
        return _public(ligne) if ligne else None


def creer(nom, mot_de_passe):
    nom = _verifier_nom(nom)
    erreur = mots_de_passe.controler_force(mot_de_passe)
    if erreur:
        raise ErreurUtilisateur(erreur)
    with db.connexion() as con:
        if con.execute("SELECT 1 FROM utilisateurs WHERE nom = ?", (nom,)).fetchone():
            raise ErreurUtilisateur(f"Le nom « {nom} » existe déjà.")
        cur = con.execute("INSERT INTO utilisateurs (nom, mdp_hash, cree_le) VALUES (?, ?, ?)",
                          (nom, mots_de_passe.hacher(mot_de_passe), _maintenant()))
        return cur.lastrowid


def authentifier(nom, mot_de_passe):
    """Renvoie l'utilisateur si le nom et le mot de passe sont bons, sinon None."""
    with db.connexion() as con:
        ligne = con.execute("SELECT * FROM utilisateurs WHERE nom = ?", ((nom or "").strip(),)).fetchone()
        if not ligne:
            mots_de_passe.verifier(mot_de_passe or "", mots_de_passe.hacher("x"))   # même durée que pour un vrai compte
            return None
        if not mots_de_passe.verifier(mot_de_passe or "", ligne["mdp_hash"]):
            return None
        con.execute("UPDATE utilisateurs SET derniere_connexion = ? WHERE id = ?", (_maintenant(), ligne["id"]))
        return {**_public(ligne), "version_jeton": ligne["version_jeton"]}


def supprimer(utilisateur_id, par_id):
    if utilisateur_id == par_id:
        raise ErreurUtilisateur("Vous ne pouvez pas supprimer votre propre compte.")
    with db.connexion() as con:
        if con.execute("SELECT COUNT(*) FROM utilisateurs").fetchone()[0] <= 1:
            raise ErreurUtilisateur("Impossible de supprimer le dernier compte.")
        cur = con.execute("DELETE FROM utilisateurs WHERE id = ?", (utilisateur_id,))
        if cur.rowcount == 0:
            raise ErreurUtilisateur("Utilisateur introuvable.")


def reinitialiser_mot_de_passe(utilisateur_id, nouveau):
    """Définit un nouveau mot de passe ; les sessions ouvertes de ce compte sont fermées."""
    erreur = mots_de_passe.controler_force(nouveau)
    if erreur:
        raise ErreurUtilisateur(erreur)
    with db.connexion() as con:
        cur = con.execute("UPDATE utilisateurs SET mdp_hash = ?, version_jeton = version_jeton + 1 WHERE id = ?",
                          (mots_de_passe.hacher(nouveau), utilisateur_id))
        if cur.rowcount == 0:
            raise ErreurUtilisateur("Utilisateur introuvable.")


def changer_mon_mot_de_passe(utilisateur_id, ancien, nouveau):
    with db.connexion() as con:
        ligne = con.execute("SELECT * FROM utilisateurs WHERE id = ?", (utilisateur_id,)).fetchone()
    if not ligne or not mots_de_passe.verifier(ancien or "", ligne["mdp_hash"]):
        raise ErreurUtilisateur("Le mot de passe actuel est incorrect.")
    reinitialiser_mot_de_passe(utilisateur_id, nouveau)


def changer_mon_nom(utilisateur_id, nouveau_nom, mot_de_passe):
    nouveau_nom = _verifier_nom(nouveau_nom)
    with db.connexion() as con:
        ligne = con.execute("SELECT * FROM utilisateurs WHERE id = ?", (utilisateur_id,)).fetchone()
        if not ligne or not mots_de_passe.verifier(mot_de_passe or "", ligne["mdp_hash"]):
            raise ErreurUtilisateur("Le mot de passe est incorrect.")
        autre = con.execute("SELECT id FROM utilisateurs WHERE nom = ? AND id <> ?", (nouveau_nom, utilisateur_id)).fetchone()
        if autre:
            raise ErreurUtilisateur(f"Le nom « {nouveau_nom} » existe déjà.")
        con.execute("UPDATE utilisateurs SET nom = ? WHERE id = ?", (nouveau_nom, utilisateur_id))


# ---- sessions -------------------------------------------------------------------
def ouvrir_session(utilisateur):
    return sessions.creer_jeton(utilisateur["id"], utilisateur["version_jeton"], db.secret_signature(), config.DUREE_SESSION_S)


def utilisateur_de_session(jeton):
    """Utilisateur correspondant à un cookie de session valide, sinon None."""
    if not jeton:
        return None
    contenu = sessions.lire_jeton(jeton, db.secret_signature())
    if not contenu:
        return None
    with db.connexion() as con:
        ligne = con.execute("SELECT * FROM utilisateurs WHERE id = ?", (contenu["u"],)).fetchone()
    if not ligne or ligne["version_jeton"] != contenu["v"]:
        return None
    return _public(ligne)
