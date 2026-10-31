"""L'adapter Excel (COM) sur Windows : pywin32 s'importe et le déroulé va jusqu'au lancement d'Excel.
Les machines de la CI Windows n'ont pas Excel : l'écriture doit alors échouer proprement sur une erreur COM,
sans rien écrire. Sur un PC avec Excel, la ligne doit être ajoutée. Ignoré hors Windows."""
import os
import shutil
import sys
import tempfile
import unittest

from backend import config
from backend.services import donnees, ecriture, listes, reglages
from backend.services.regles import traiter
from outils.donnees_fictives import creer_classeur


@unittest.skipUnless(sys.platform == "win32", "Excel (COM) n'existe que sous Windows")
class TestAdapterExcelWindows(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.avant = (config.DB_PATH, config.FICHIER, config.DOSSIER_SAUVEGARDES)
        config.DB_PATH = os.path.join(self.dossier, "demo.sqlite3")
        config.FICHIER = os.path.join(self.dossier, "demo.xlsx")
        config.DOSSIER_SAUVEGARDES = os.path.join(self.dossier, "sauvegardes")
        creer_classeur(config.FICHIER)
        for cache in (donnees._cache, donnees._cache_t, listes._cache):
            cache["mtime"] = None
        reglages._cache.update(cle=None, config=None)

    def tearDown(self):
        config.DB_PATH, config.FICHIER, config.DOSSIER_SAUVEGARDES = self.avant
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_ecriture_par_excel_ou_erreur_com_propre(self):
        import pywintypes
        from backend.services.classeur_excel import ClasseurExcel
        saisie = {"Matricule monteur": "1001", "Format": "2", "Matière": "I", "Face": "A", "N° article meule": "0101",
                  "Lot fournisseur N° FA / Beleg": "123", "Date montage": "2026-10-20", "N° de Machine": "s1", "MA5": "Oui",
                  "Pression d'arrosage": 6, "Vitesse de rotation": 32, "V.Avance": 850, "Hauteur meule initiale, mm": 89,
                  "Compteur début": 0, "Matricule démonteur": "1002", "Compteur fin": 2500, "Hauteur meule finale, mm": 0}
        propres, erreurs, _ = traiter(saisie)
        self.assertEqual(erreurs, [])
        with open(config.FICHIER, "rb") as fichier:
            avant = fichier.read()
        try:
            ligne, _, _ = ecriture.ajouter_ligne(propres, classeur=ClasseurExcel())
        except pywintypes.com_error:                    # pas d'Excel sur cette machine
            with open(config.FICHIER, "rb") as fichier:
                self.assertEqual(fichier.read(), avant)
        else:                                           # Excel présent : la ligne est bien là
            self.assertGreater(ligne, 1)
        self.assertFalse(ecriture.VERROU.locked())


if __name__ == "__main__":
    unittest.main()
