import unittest

from backend.auth import mots_de_passe


class TestMotsDePasse(unittest.TestCase):
    def test_un_mot_de_passe_se_verifie(self):
        empreinte = mots_de_passe.hacher("correct horse")
        self.assertTrue(mots_de_passe.verifier("correct horse", empreinte))

    def test_un_mauvais_mot_de_passe_est_refuse(self):
        empreinte = mots_de_passe.hacher("correct horse")
        self.assertFalse(mots_de_passe.verifier("correct hors", empreinte))
        self.assertFalse(mots_de_passe.verifier("", empreinte))

    def test_le_mot_de_passe_n_apparait_pas_dans_l_empreinte(self):
        self.assertNotIn("secret123", mots_de_passe.hacher("secret123"))

    def test_deux_empreintes_du_meme_mot_de_passe_different(self):
        self.assertNotEqual(mots_de_passe.hacher("abcdefgh"), mots_de_passe.hacher("abcdefgh"))

    def test_une_empreinte_abimee_est_refusee_sans_erreur(self):
        for empreinte in ("", "n'importe quoi", "scrypt$1$2", "md5$1$2$3$4$5"):
            self.assertFalse(mots_de_passe.verifier("abcdefgh", empreinte))

    def test_longueur_minimale(self):
        self.assertIsNotNone(mots_de_passe.controler_force("court"))
        self.assertIsNone(mots_de_passe.controler_force("12345678"))
        self.assertIsNotNone(mots_de_passe.controler_force(None))


if __name__ == "__main__":
    unittest.main()
