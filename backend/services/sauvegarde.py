"""Copie de sécurité du classeur avant chaque écriture (data/sauvegardes, les 30 dernières sont gardées).
Une copie qui échoue (disque plein, dossier inaccessible) ne bloque pas la saisie : l'erreur s'affiche dans la fenêtre du serveur."""
import datetime
import os
import shutil

from .. import config

GARDER = 30


def sauvegarder(chemin, dossier=None, garder=GARDER):
    """Copie `chemin` dans le dossier des sauvegardes. Renvoie le chemin de la copie, ou None si la copie a échoué."""
    dossier = dossier or config.DOSSIER_SAUVEGARDES
    try:
        os.makedirs(dossier, exist_ok=True)
        nom, extension = os.path.splitext(os.path.basename(chemin))
        copie = os.path.join(dossier, f"{nom}_{datetime.datetime.now():%Y%m%d_%H%M%S_%f}{extension}")
        shutil.copy2(chemin, copie)
        _purger(dossier, nom, extension, garder)
        return copie
    except OSError as erreur:
        print(f"[sauvegarde] Copie de sécurité impossible : {erreur}", flush=True)
        return None


def _purger(dossier, nom, extension, garder):
    copies = sorted(fichier for fichier in os.listdir(dossier) if fichier.startswith(nom + "_") and fichier.endswith(extension))
    for ancienne in copies[:-garder] if garder > 0 else copies:
        try:
            os.remove(os.path.join(dossier, ancienne))
        except OSError:
            pass
