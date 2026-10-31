"""Copie de sécurité, déconnexion, limiteur, format des scripts Windows."""
import glob
import os
import shutil
import tempfile
import unittest

from backend.auth import sessions, utilisateurs
from backend.services import sauvegarde
from tests.utilitaires import BaseTest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSauvegarde(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.mkdtemp()
        self.source = os.path.join(self.dossier, "suivi.xlsx")
        with open(self.source, "wb") as fichier:
            fichier.write(b"contenu")
        self.copies = os.path.join(self.dossier, "sauvegardes")

    def tearDown(self):
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_copie_identique(self):
        copie = sauvegarde.sauvegarder(self.source, dossier=self.copies)
        with open(copie, "rb") as fichier:
            self.assertEqual(fichier.read(), b"contenu")

    def test_garde_seulement_les_dernieres(self):
        for _ in range(7):
            sauvegarde.sauvegarder(self.source, dossier=self.copies, garder=3)
        self.assertEqual(len(os.listdir(self.copies)), 3)

    def test_echec_de_copie_ne_leve_pas(self):
        self.assertIsNone(sauvegarde.sauvegarder(os.path.join(self.dossier, "absent.xlsx"), dossier=self.copies))


class TestSecurite(BaseTest):
    def test_deconnexion_invalide_le_jeton(self):
        utilisateurs.creer("alice", "motdepasse1")
        compte = utilisateurs.authentifier("alice", "motdepasse1")
        jeton = utilisateurs.ouvrir_session(compte)
        self.assertIsNotNone(utilisateurs.utilisateur_de_session(jeton))
        utilisateurs.fermer_sessions(compte["id"])
        self.assertIsNone(utilisateurs.utilisateur_de_session(jeton))

    def test_limiteur_ne_garde_pas_d_entree_vide_et_reste_borne(self):
        limiteur = sessions.Limiteur(maxi=3, fenetre_s=60)
        for i in range(100):
            self.assertFalse(limiteur.bloque(f"nom{i}"))
        self.assertEqual(len(limiteur._echecs), 0)
        for i in range(6000):
            limiteur.echec(f"nom{i}")
        self.assertLessEqual(len(limiteur._echecs), 5000)
        for _ in range(3):
            limiteur.echec("cible")
        self.assertTrue(limiteur.bloque("cible"))


class TestScriptsWindows(unittest.TestCase):
    def test_bat_et_ps1_en_ascii_avec_fins_de_ligne_windows(self):
        fichiers = glob.glob(os.path.join(RACINE, "scripts", "*.bat")) + glob.glob(os.path.join(RACINE, "scripts", "*.ps1"))
        self.assertTrue(fichiers)
        for chemin in fichiers:
            with open(chemin, "rb") as fichier:
                brut = fichier.read()
            nom = os.path.basename(chemin)
            if nom == "preparer_python.ps1":          # script hérité, non modifié ici
                continue
            self.assertTrue(all(octet < 128 for octet in brut), f"{nom} : caractère non ASCII")
            self.assertEqual(brut.count(b"\n"), brut.count(b"\r\n"), f"{nom} : fins de ligne non CRLF")


if __name__ == "__main__":
    unittest.main()
