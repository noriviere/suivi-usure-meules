"""Construit la démo en ligne (dossier docs/, publiable avec GitHub Pages).

    python -m outils.construire_demo_web

La démo est 100 % statique : elle ne contient AUCUNE donnée réelle. Le script
  1. fabrique un classeur de fausses données (outils/donnees_fictives.py) dans un dossier temporaire,
  2. relit ce classeur avec le vrai code Python de l'application et enregistre le résultat dans docs/demo_data.json,
  3. copie la page web (frontend/) en adaptant les chemins, et ajoute demo_web/demo-api.js,
     un faux serveur en JavaScript qui rejoue les contrôles de saisie dans le navigateur.
Rien n'est écrit nulle part : les saisies de la démo restent dans la page."""
import json
import os
import re
import shutil
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)
os.environ.setdefault("MEULES_DEMO", "1")

from backend import config                                    # noqa: E402
from backend.services import donnees, listes, reglages       # noqa: E402
from backend.services.controle import anomalies               # noqa: E402
from backend.services.regles import perte_annuelle            # noqa: E402
from outils.donnees_fictives import creer_classeur            # noqa: E402

SORTIE = os.path.join(RACINE, "docs")
BANDEAU = "DÉMO EN LIGNE : données entièrement inventées. Les saisies sont contrôlées comme en vrai mais ne sont enregistrées nulle part."


def instantane(dossier_temp):
    config.DB_PATH = os.path.join(dossier_temp, "demo.sqlite3")
    config.FICHIER = os.path.join(dossier_temp, "demo.xlsx")
    creer_classeur(config.FICHIER)
    for cache in (donnees._cache, donnees._cache_t, listes._cache):
        cache["mtime"] = None
    reglages._cache.update(cle=None, config=None)
    reference = listes.charger()
    return {
        "etat": {"test": False, "demo": True, "fichier": "classeur_demo.xlsx", "existe": True},
        "champs": reglages.config(),
        "listes": listes.listes_deroulantes(),
        "formats": reference["formats"],
        "meules": reference["meules"],
        "donnees": donnees.tableau(),
        "anomalies": anomalies(),
        "perte": perte_annuelle(),
        "reglages": reglages.etat(),
        "date_construction": __import__("datetime").date.today().isoformat(),
    }


def adapter_html(texte, scripts_avant=()):
    texte = texte.replace('href="/static/', 'href="static/').replace('src="/static/', 'src="static/')
    texte = texte.replace('href="/consultation"', 'href="consultation.html"').replace('href="/"', 'href="index.html"')
    texte = texte.replace('href="/admin"', 'href="admin.html"')
    for script in scripts_avant:                                                    # le faux serveur passe avant tout le reste
        texte = texte.replace("<script ", f'<script src="{script}"></script>\n  <script ', 1)
    return texte


def construire():
    with tempfile.TemporaryDirectory() as dossier_temp:
        donnees_demo = instantane(dossier_temp)
    if os.path.isdir(SORTIE):
        shutil.rmtree(SORTIE)
    os.makedirs(SORTIE)
    shutil.copytree(os.path.join(RACINE, "frontend", "css"), os.path.join(SORTIE, "static", "css"))
    shutil.copytree(os.path.join(RACINE, "frontend", "js"), os.path.join(SORTIE, "static", "js"))
    shutil.copytree(os.path.join(RACINE, "frontend", "img"), os.path.join(SORTIE, "static", "img"))
    # les chemins d'images de champs.json (« /static/img/... ») deviennent relatifs
    donnees_demo_texte = json.dumps(donnees_demo, ensure_ascii=False).replace('"/static/img/', '"static/img/')
    with open(os.path.join(SORTIE, "demo_data.json"), "w", encoding="utf-8") as fichier:
        fichier.write(donnees_demo_texte)
    shutil.copy(os.path.join(RACINE, "demo_web", "demo-api.js"), os.path.join(SORTIE, "demo-api.js"))
    # les liens construits en JavaScript par la page d'administration deviennent relatifs
    chemin_admin_js = os.path.join(SORTIE, "static", "js", "admin.js")
    with open(chemin_admin_js, encoding="utf-8") as fichier:
        code = fichier.read()
    for ancien, nouveau in (('href: "/consultation"', 'href: "consultation.html"'), ('href: "/"', 'href: "index.html"')):
        assert ancien in code, ancien
        code = code.replace(ancien, nouveau)
    with open(chemin_admin_js, "w", encoding="utf-8") as fichier:
        fichier.write(code)
    for source, cible in (("index.html", "index.html"), ("consultation.html", "consultation.html"), ("admin.html", "admin.html")):
        with open(os.path.join(RACINE, "frontend", "html", source), encoding="utf-8") as fichier:
            texte = adapter_html(fichier.read(), scripts_avant=("demo-api.js",))
        with open(os.path.join(SORTIE, cible), "w", encoding="utf-8") as fichier:
            fichier.write(texte)
    open(os.path.join(SORTIE, ".nojekyll"), "w").close()
    print(f"Démo construite dans {SORTIE} ({len(donnees_demo['donnees']['lignes'])} lignes fictives).")


if __name__ == "__main__":
    construire()
