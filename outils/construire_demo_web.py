"""Construit la démo en ligne (dossier docs/, publiable avec GitHub Pages).

    python -m outils.construire_demo_web            reconstruit docs/
    python -m outils.construire_demo_web --check    dit si docs/ est à jour, sans rien écrire (code de sortie 1 sinon)

La démo est 100 % statique : elle ne contient AUCUNE donnée réelle. Le script
  1. fabrique un classeur de fausses données (outils/donnees_fictives.py) dans un dossier temporaire,
  2. relit ce classeur avec le vrai code Python de l'application et enregistre le résultat dans docs/demo_data.json,
  3. copie la page web (frontend/) en adaptant les chemins, et ajoute demo_web/demo-api.js,
     un faux serveur en JavaScript qui rejoue les contrôles de saisie dans le navigateur.
Rien n'est écrit nulle part : les saisies de la démo restent dans la page."""
import argparse
import datetime
import json
import os
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
A_GARDER = ("agents", "adr")                                  # docs/ écrits à la main pour les agents, pas par ce script
# Date fixe des fausses données : la démo est identique d'une construction à l'autre (pas de faux diff dans docs/).
# Le navigateur recale de toute façon les dates sur le jour d'ouverture (decalerDates dans demo-api.js).
DATE_REFERENCE = datetime.date(2026, 10, 31)
BANDEAU = "DÉMO EN LIGNE : données entièrement inventées. Les saisies sont contrôlées comme en vrai mais ne sont enregistrées nulle part."


def instantane(dossier_temp):
    config.DB_PATH = os.path.join(dossier_temp, "demo.sqlite3")
    config.FICHIER = os.path.join(dossier_temp, "demo.xlsx")
    creer_classeur(config.FICHIER, aujourdhui=DATE_REFERENCE)
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
        "perte": perte_annuelle(DATE_REFERENCE.year),
        "reglages": reglages.etat(),
        "date_construction": DATE_REFERENCE.isoformat(),
    }


def adapter_html(texte, scripts_avant=()):
    texte = texte.replace('href="/static/', 'href="static/').replace('src="/static/', 'src="static/')
    texte = texte.replace('href="/consultation"', 'href="consultation.html"').replace('href="/"', 'href="index.html"')
    texte = texte.replace('href="/admin"', 'href="admin.html"')
    for script in scripts_avant:                                                    # le faux serveur passe avant tout le reste
        texte = texte.replace("<script ", f'<script src="{script}"></script>\n  <script ', 1)
    return texte


def construire(sortie=SORTIE):
    with tempfile.TemporaryDirectory() as dossier_temp:
        donnees_demo = instantane(dossier_temp)
    os.makedirs(sortie, exist_ok=True)
    for nom in os.listdir(sortie):
        if nom in A_GARDER:
            continue
        chemin = os.path.join(sortie, nom)
        if os.path.isdir(chemin):
            shutil.rmtree(chemin)
        else:
            os.remove(chemin)
    for dossier in ("css", "js", "img"):
        shutil.copytree(os.path.join(RACINE, "frontend", dossier), os.path.join(sortie, "static", dossier))
    # les chemins d'images de champs.json (« /static/img/... ») deviennent relatifs
    donnees_demo_texte = json.dumps(donnees_demo, ensure_ascii=False).replace('"/static/img/', '"static/img/')
    with open(os.path.join(sortie, "demo_data.json"), "w", encoding="utf-8") as fichier:
        fichier.write(donnees_demo_texte)
    shutil.copy(os.path.join(RACINE, "demo_web", "demo-api.js"), os.path.join(sortie, "demo-api.js"))
    # les liens construits en JavaScript par la page d'administration deviennent relatifs
    chemin_admin_js = os.path.join(sortie, "static", "js", "admin.js")
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
        with open(os.path.join(sortie, cible), "w", encoding="utf-8") as fichier:
            fichier.write(texte)
    open(os.path.join(sortie, ".nojekyll"), "w").close()
    return len(donnees_demo["donnees"]["lignes"])


def ecarts(sortie=SORTIE):
    """Fichiers de sortie qui diffèrent d'une construction neuve (modifiés, en trop, manquants), sans rien écrire dans sortie."""
    with tempfile.TemporaryDirectory() as dossier_temp:
        construction_neuve = os.path.join(dossier_temp, "docs")
        construire(construction_neuve)
        attendus, presents = _fichiers(construction_neuve), _fichiers(sortie)
        ecarts_trouves = [f"modifié : {nom}" for nom in sorted(attendus & presents)
                          if _contenu(os.path.join(construction_neuve, nom)) != _contenu(os.path.join(sortie, nom))]
    ecarts_trouves += [f"en trop : {nom}" for nom in sorted(presents - attendus)]
    ecarts_trouves += [f"manquant : {nom}" for nom in sorted(attendus - presents)]
    return ecarts_trouves


def _contenu(chemin):
    """Contenu du fichier, fins de ligne Windows ramenées à celles de Linux (git les convertit au checkout sous Windows)."""
    with open(chemin, "rb") as fichier:
        return fichier.read().replace(b"\r\n", b"\n")


def _fichiers(dossier):
    """Chemins relatifs de tous les fichiers du dossier, hors dossiers écrits à la main (A_GARDER)."""
    if not os.path.isdir(dossier):
        return set()
    return {os.path.relpath(os.path.join(racine, nom), dossier)
            for racine, _, noms in os.walk(dossier) for nom in noms
            if os.path.relpath(racine, dossier).split(os.sep)[0] not in A_GARDER}


def main(arguments=None, sortie=SORTIE):
    analyseur = argparse.ArgumentParser(prog="python -m outils.construire_demo_web", description="Construit la démo en ligne dans docs/.")
    analyseur.add_argument("--check", action="store_true", help="dit si docs/ est à jour, sans rien écrire (code de sortie 1 sinon)")
    if not analyseur.parse_args(arguments).check:
        nombre = construire(sortie)
        print(f"Démo construite dans {sortie} ({nombre} lignes fictives).")
        return 0
    ecarts_trouves = ecarts(sortie)
    if not ecarts_trouves:
        print(f"La démo dans {sortie} est à jour.")
        return 0
    print(f"La démo dans {sortie} n'est pas à jour :")
    for ecart in ecarts_trouves:
        print(f"  {ecart}")
    print("Lancer python -m outils.construire_demo_web puis commiter docs/.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
