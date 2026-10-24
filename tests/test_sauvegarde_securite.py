"""Copie de sécurité, déconnexion, limiteur, mode strict de l'écriture démo, format des scripts Windows."""
import glob
import os
import shutil
import tempfile
import unittest

from backend import config
from backend.auth import sessions, utilisateurs
from backend.services import donnees, listes, reglages, sauvegarde
from backend.services.ecriture_demo import ajouter_ligne
from backend.services.regles import traiter
from outils.donnees_fictives import creer_classeur
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


class TestEcritureDemo(unittest.TestCase):
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
        self.saisie = {"Matricule monteur": "1001", "Format": "2", "Matière": "I", "Face": "A", "N° article meule": "0101",
                       "Lot fournisseur N° FA / Beleg": "123", "Date montage": "2026-10-20", "N° de Machine": "s1", "MA5": "Oui",
                       "Pression d'arrosage": 6, "Vitesse de rotation": 32, "V.Avance": 850, "Hauteur meule initiale, mm": 89,
                       "Compteur début": 0, "Matricule démonteur": "1002", "Compteur fin": 2500, "Hauteur meule finale, mm": 0}

    def tearDown(self):
        config.DB_PATH, config.FICHIER, config.DOSSIER_SAUVEGARDES = self.avant
        shutil.rmtree(self.dossier, ignore_errors=True)

    def test_une_copie_de_securite_est_faite_avant_ecriture(self):
        propres, erreurs, _ = traiter(self.saisie)
        self.assertEqual(erreurs, [])
        ajouter_ligne(propres)
        copies = glob.glob(os.path.join(config.DOSSIER_SAUVEGARDES, "*.xlsx"))
        self.assertEqual(len(copies), 1)

    def test_meule_non_finie_copiee_dans_l_onglet_defaut(self):
        saisie = {**self.saisie, "Hauteur meule finale, mm": 10, "Commentaire": "Meule cassée ou fissurée : fissure"}
        propres, erreurs, _ = traiter(saisie)
        self.assertEqual(erreurs, [])
        ligne, _, info = ajouter_ligne(propres, defaut=True)
        self.assertEqual(info["onglet"], "Data defaut")
        self.assertGreater(info["ligne"], 1)

    def test_colonne_inconnue_refusee_sans_ecriture_partielle(self):
        propres, _, _ = traiter(self.saisie)
        propres["Colonne qui n'existe pas"] = 1
        with self.assertRaises(ValueError):
            ajouter_ligne(propres)
        for cache in (donnees._cache_t,):
            cache["mtime"] = None
        self.assertEqual(len(donnees.tableau()["lignes"]), 320)


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
