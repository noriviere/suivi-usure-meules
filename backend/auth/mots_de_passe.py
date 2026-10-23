"""Hachage des mots de passe avec scrypt (bibliothèque standard, rien à installer)."""
import base64
import hashlib
import hmac
import os

COUT_CPU, TAILLE_BLOC, PARALLELISME = 2 ** 14, 8, 1
LONGUEUR_MINI = 8


def _b64(octets):
    return base64.b64encode(octets).decode("ascii")


def hacher(mot_de_passe):
    sel = os.urandom(16)
    condensat = hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=sel, n=COUT_CPU, r=TAILLE_BLOC, p=PARALLELISME, dklen=32)
    return f"scrypt${COUT_CPU}${TAILLE_BLOC}${PARALLELISME}${_b64(sel)}${_b64(condensat)}"


def verifier(mot_de_passe, empreinte):
    try:
        algo, cout_cpu, taille_bloc, parallelisme, sel, condensat = empreinte.split("$")
        if algo != "scrypt":
            return False
        attendu = base64.b64decode(condensat)
        calcule = hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=base64.b64decode(sel),
                                 n=int(cout_cpu), r=int(taille_bloc), p=int(parallelisme), dklen=len(attendu))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calcule, attendu)


def controler_force(mot_de_passe):
    """Renvoie un message d'erreur, ou None si le mot de passe convient."""
    if len(mot_de_passe or "") < LONGUEUR_MINI:
        return f"Le mot de passe doit contenir au moins {LONGUEUR_MINI} caractères."
    return None
