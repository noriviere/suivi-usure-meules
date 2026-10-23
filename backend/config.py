"""Chemins et réglages généraux. Les autres modules lisent ces valeurs au moment de l'appel
(config.FICHIER, config.DB_PATH...), ce qui permet aux tests de les remplacer."""
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # dossier mon-app
DOSSIER_CONFIG = os.path.join(RACINE, "config")
DOSSIER_DONNEES = os.path.join(RACINE, "data")
DOSSIER_FRONTEND = os.path.join(RACINE, "frontend")

MODE_TEST = False     # True : copie de test ; False : fichier de PRODUCTION
# Mode démonstration : classeur de FAUSSES données, sans Excel (fonctionne sous Linux, macOS, Codespaces).
# Se lance avec la variable d'environnement MEULES_DEMO=1 (voir scripts/lancer_demo.bat et .sh).
MODE_DEMO = os.environ.get("MEULES_DEMO", "").strip().lower() in ("1", "true", "oui")
DOSSIER_DEMO = os.path.join(DOSSIER_DONNEES, "demo")

FICHIER_TEST = os.path.join(DOSSIER_DONNEES, "copie_app_test.xlsx")
FICHIER_PROD_PAR_DEFAUT = os.path.join(DOSSIER_DONNEES, "classeur_meules.xlsx")
CHAMPS_JSON = os.path.join(DOSSIER_CONFIG, "champs.json")
DB_PATH = os.path.join(DOSSIER_DONNEES, "application.sqlite3")      # utilisateurs, règles métier, historique


def _chemin_prod():
    """Le trajet du vrai fichier se met dans config/chemin_fichier.txt (une seule ligne,
    ex. \\\\SERVEUR\\Partage\\suivi_meules.xlsx ou D:\\Meulage\\fichier.xlsx ; scripts\\choisir_fichier.bat l'écrit pour vous).
    Sans ce fichier, on prend data/classeur_meules.xlsx, ou à défaut le seul autre .xlsx du dossier data."""
    chemin_reglage = os.path.join(DOSSIER_CONFIG, "chemin_fichier.txt")
    if os.path.exists(chemin_reglage):
        with open(chemin_reglage, encoding="utf-8-sig") as fichier:
            ligne = fichier.readline().strip().strip('"')
        if ligne:
            return ligne
    if not os.path.exists(FICHIER_PROD_PAR_DEFAUT) and os.path.isdir(DOSSIER_DONNEES):
        autres = [nom for nom in os.listdir(DOSSIER_DONNEES)
                  if nom.lower().endswith(".xlsx") and not nom.startswith("~$") and nom != os.path.basename(FICHIER_TEST)]
        if len(autres) == 1:
            return os.path.join(DOSSIER_DONNEES, autres[0])
    return FICHIER_PROD_PAR_DEFAUT


FICHIER = FICHIER_TEST if MODE_TEST else _chemin_prod()
JOURNAL = os.path.join(DOSSIER_DONNEES, "journal_saisies_test.csv" if MODE_TEST else "journal_saisies.csv")
JOURNAL_CHRONO = os.path.join(DOSSIER_DONNEES, "journal_chrono_test.csv" if MODE_TEST else "journal_chrono.csv")

if MODE_DEMO:                      # tout est séparé des vraies données
    FICHIER = os.path.join(DOSSIER_DEMO, "classeur_demo.xlsx")
    DB_PATH = os.path.join(DOSSIER_DEMO, "application_demo.sqlite3")
    JOURNAL = os.path.join(DOSSIER_DEMO, "journal_saisies_demo.csv")
    JOURNAL_CHRONO = os.path.join(DOSSIER_DEMO, "journal_chrono_demo.csv")
COMPTE_DEMO = ("demo", "demo-meules")      # compte du back-office en mode démo (jamais utilisé en production)

# Session du back-office
DUREE_SESSION_S = 8 * 3600
COOKIE_SESSION = "session_meules"
