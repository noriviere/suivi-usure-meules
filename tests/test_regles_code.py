"""Règles de CONTRIBUTING.md vérifiables automatiquement : elles tournent avec les autres tests (CI, scripts/tests.bat)."""
import ast
import glob
import os
import re
import unittest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIERS = ("backend", "outils", "tests", "scripts")

# Seuls ces fichiers peuvent ouvrir le classeur en écriture (Excel par COM, ou enregistrement openpyxl).
ECRITURE_AUTORISEE = {
    "backend/services/classeur_excel.py",       # adapter de production
    "backend/services/classeur_openpyxl.py",    # adapter démo et tests
    "outils/nettoyage.py",                      # outil lancé à la main, serveur arrêté
    "outils/donnees_fictives.py",               # fabrique le classeur de fausses données
}
ECRITURE = re.compile(r"win32com|Workbooks\.Open|\.save\(")


def _fichiers_python():
    for dossier in DOSSIERS:
        for chemin in glob.glob(os.path.join(RACINE, dossier, "**", "*.py"), recursive=True):
            yield os.path.relpath(chemin, RACINE).replace(os.sep, "/"), chemin


def _noms_definis(arbre):
    """Les noms que le code crée : variables, paramètres, fonctions, classes, exceptions capturées."""
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name) and isinstance(noeud.ctx, ast.Store):
            yield noeud.lineno, noeud.id
        elif isinstance(noeud, ast.arg):
            yield noeud.lineno, noeud.arg
        elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield noeud.lineno, noeud.name
        elif isinstance(noeud, ast.ExceptHandler) and noeud.name:
            yield noeud.lineno, noeud.name


class TestReglesDeCode(unittest.TestCase):
    def test_pas_de_nom_d_une_seule_lettre(self):
        """CONTRIBUTING : noms de variables explicites (pas de lettres seules). « _ » reste permis pour une valeur ignorée."""
        fautes = []
        for relatif, chemin in _fichiers_python():
            with open(chemin, encoding="utf-8") as fichier:
                arbre = ast.parse(fichier.read(), relatif)
            fautes += [f"{relatif}:{ligne} « {nom} »" for ligne, nom in _noms_definis(arbre) if len(nom) == 1 and nom != "_"]
        self.assertEqual(fautes, [], "Noms d'une seule lettre : renommez-les")

    def test_seuls_les_adapters_ecrivent_dans_le_classeur(self):
        """CONTRIBUTING : toute saisie est écrite par ecriture.ajouter_ligne, via un adapter."""
        fautifs = []
        for relatif, chemin in _fichiers_python():
            if relatif.startswith("tests/") or relatif in ECRITURE_AUTORISEE:
                continue
            with open(chemin, encoding="utf-8") as fichier:
                if ECRITURE.search(fichier.read()):
                    fautifs.append(relatif)
        self.assertEqual(fautifs, [], "Écriture du classeur hors des adapters : passez par ecriture.ajouter_ligne")


if __name__ == "__main__":
    unittest.main()
