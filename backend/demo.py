"""Préparation du mode démonstration (MEULES_DEMO=1) : classeur de fausses données + compte du back-office."""
import datetime
import os

from . import config


def preparer():
    """Crée, si besoin, le classeur de démonstration et le compte de démo. Sans effet hors mode démo."""
    if not config.MODE_DEMO:
        return
    from outils.donnees_fictives import creer_classeur
    from .auth import utilisateurs
    os.makedirs(config.DOSSIER_DEMO, exist_ok=True)
    # classeur fictif recréé chaque jour : ses dates sont calculées à partir d'aujourd'hui (les saisies faites en démo ne sont pas gardées)
    if os.path.exists(config.FICHIER) and datetime.date.fromtimestamp(os.path.getmtime(config.FICHIER)) < datetime.date.today():
        os.remove(config.FICHIER)
    if not os.path.exists(config.FICHIER):
        creer_classeur(config.FICHIER)
    if utilisateurs.nombre() == 0:
        utilisateurs.creer(*config.COMPTE_DEMO)
