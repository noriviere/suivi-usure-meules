import unittest

from backend.services import donnees, listes
from tests.utilitaires import BaseTest, ligne_data


class TestNorm(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(donnees.norm("  Hauteur   Meule\ninitiale "), "hauteur meule initiale")
        self.assertEqual(donnees.norm(None), "")
        self.assertEqual(donnees.norm(5), "5")


class TestLectureClasseur(BaseTest):
    lignes = [ligne_data(**{"Matricule monteur": "123", "Compteur fin": 1000, "Nb faces/meule de 89 mm": 1000}),
              ligne_data(**{"Face": "B", "Nb faces/meule de 89 mm": 1200}),
              ligne_data(**{"Matricule monteur": "0123", "Face": "A", "Nb faces/meule de 89 mm": 1400}),
              ligne_data(**{"Face": "A", "Nb faces/meule de 89 mm": 1600}),
              ligne_data(**{"N° article meule": None})]          # ligne sans article : ignorée

    def test_les_lignes_sans_article_sont_ignorees(self):
        self.assertEqual(len(donnees.lire_data()), 4)

    def test_tableau(self):
        tableau_lu = donnees.tableau()
        self.assertEqual(len(tableau_lu["lignes"]), 4)
        self.assertEqual(tableau_lu["lignes"][0][0], 2)                     # numéro de ligne Excel
        self.assertEqual(tableau_lu["entetes"][0], "Matricule monteur")
        self.assertEqual(tableau_lu["cles"][5], "n° article meule")
        self.assertEqual(tableau_lu["lignes"][0][tableau_lu["cles"].index("date montage") + 1], "2026-05-04")

    def test_matricules_completes_a_4_chiffres(self):
        self.assertEqual(donnees.matricules(), ["0123"])           # « 123 » et « 0123 » sont la même personne

    def test_mediane_par_face(self):
        resultat = donnees.mediane("0105", "s7", "I", minimum=2)
        self.assertEqual(resultat["A"]["mediane"], 1400)
        self.assertEqual(resultat["A"]["nb_cas"], 3)
        self.assertTrue(resultat["A"]["fiable"])
        self.assertEqual(resultat["B"]["mediane"], 1200)
        self.assertFalse(resultat["B"]["fiable"] and resultat["B"]["nb_cas"] >= 2)

    def test_mediane_elargit_le_critere_si_peu_de_cas(self):
        resultat = donnees.mediane("0105", "s99", "I", minimum=1)         # aucune ligne pour la machine s99
        self.assertEqual(resultat["A"]["critere"], "article + matière")

    def test_mediane_sans_aucune_donnee(self):
        self.assertEqual(donnees.mediane("0000", "s1", "I"), {"A": None, "B": None})

    def test_listes_deroulantes(self):
        listes_lues = listes.listes_deroulantes()
        self.assertEqual(listes_lues["Format"], ["8"])
        self.assertEqual(listes_lues["Matière"], ["I", "C"])
        self.assertEqual(listes_lues["N° de Machine"], ["s1", "s7"])
        self.assertEqual(listes_lues["N° article meule"], ["0105", "0999"])

    def test_ligne_format(self):
        reference = listes.ligne_format("8", "I")
        self.assertEqual(reference["machines"], ["s1", "s7"])
        self.assertEqual(reference["ma5"], "Non")
        self.assertIsNone(listes.ligne_format("8", "X"))


if __name__ == "__main__":
    unittest.main()
