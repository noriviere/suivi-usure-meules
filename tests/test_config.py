"""Choix du classeur de production : chemin_fichier.txt (tous encodages), classeur par défaut, installation existante."""
import os
import shutil
import tempfile
import time
import unittest

from backend import config


class TestCheminProd(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.avant = (config.DOSSIER_CONFIG, config.DOSSIER_DONNEES, config.FICHIER_PROD_PAR_DEFAUT, config.FICHIER_TEST)
        config.DOSSIER_CONFIG = os.path.join(self.dossier, "config")
        config.DOSSIER_DONNEES = os.path.join(self.dossier, "data")
        os.makedirs(config.DOSSIER_CONFIG)
        os.makedirs(config.DOSSIER_DONNEES)
        config.FICHIER_PROD_PAR_DEFAUT = os.path.join(config.DOSSIER_DONNEES, "classeur_meules.xlsx")
        config.FICHIER_TEST = os.path.join(config.DOSSIER_DONNEES, "copie_app_test.xlsx")

    def tearDown(self):
        (config.DOSSIER_CONFIG, config.DOSSIER_DONNEES, config.FICHIER_PROD_PAR_DEFAUT, config.FICHIER_TEST) = self.avant
        shutil.rmtree(self.dossier, ignore_errors=True)

    def _data(self, nom, age_s=0):
        chemin = os.path.join(config.DOSSIER_DONNEES, nom)
        open(chemin, "w").close()
        os.utime(chemin, (time.time() - age_s, time.time() - age_s))
        return chemin

    def _chemin_fichier(self, octets):
        with open(os.path.join(config.DOSSIER_CONFIG, "chemin_fichier.txt"), "wb") as fichier:
            fichier.write(octets)

    def test_sans_rien_renvoie_le_defaut(self):
        self.assertEqual(config._chemin_prod(), config.FICHIER_PROD_PAR_DEFAUT)

    def test_installation_existante_prend_le_xlsx_unique(self):
        ancien = self._data("ancien nom.xlsx")
        self.assertEqual(config._chemin_prod(), ancien)

    def test_ignore_copies_verrous_et_sauvegardes_et_prend_le_plus_recent(self):
        principal = self._data("suivi.xlsx", age_s=10)
        self._data("suivi_AVANT_NETTOYAGE_20261001.xlsx")
        self._data("~$suivi.xlsx")
        self._data("copie_app_test.xlsx")
        self.assertEqual(config._chemin_prod(), principal)

    def test_le_classeur_par_defaut_prime_sur_les_autres(self):
        defaut = self._data("classeur_meules.xlsx", age_s=100)
        self._data("autre.xlsx")
        self.assertEqual(config._chemin_prod(), defaut)

    def test_chemin_fichier_utf8_avec_bom_et_guillemets(self):
        self._chemin_fichier('\ufeff"D:\\Données\\suivi.xlsx"\r\n'.encode("utf-8"))
        self.assertEqual(config._chemin_prod(), "D:\\Données\\suivi.xlsx")

    def test_chemin_fichier_ecrit_par_un_bat_en_cp850_ne_plante_pas(self):
        self._chemin_fichier("D:\\Données\\suivi.xlsx\r\n".encode("cp850"))
        self.assertEqual(config._chemin_prod(), "D:\\Données\\suivi.xlsx")


if __name__ == "__main__":
    unittest.main()
