import unittest

from backend.auth.sessions import Limiteur, creer_jeton, lire_jeton


class TestJetons(unittest.TestCase):
    def test_jeton_valide(self):
        jeton = creer_jeton(7, 3, "cle", 100, maintenant=1000)
        self.assertEqual(lire_jeton(jeton, "cle", maintenant=1050), {"u": 7, "v": 3})

    def test_jeton_expire(self):
        jeton = creer_jeton(7, 3, "cle", 100, maintenant=1000)
        self.assertIsNone(lire_jeton(jeton, "cle", maintenant=1101))

    def test_mauvaise_cle(self):
        jeton = creer_jeton(7, 3, "cle", 100, maintenant=1000)
        self.assertIsNone(lire_jeton(jeton, "autre", maintenant=1001))

    def test_jeton_modifie(self):
        jeton = creer_jeton(7, 3, "cle", 100, maintenant=1000)
        corps, signature = jeton.split(".")
        autre = creer_jeton(1, 3, "cle", 100, maintenant=1000).split(".")[0]
        self.assertIsNone(lire_jeton(autre + "." + signature, "cle", maintenant=1001))
        self.assertIsNone(lire_jeton(corps + "." + signature[:-2] + "xx", "cle", maintenant=1001))

    def test_jetons_invalides(self):
        for jeton in (None, "", "abc", "a.b.c", "....", "é.é"):
            self.assertIsNone(lire_jeton(jeton, "cle"))


class TestLimiteur(unittest.TestCase):
    def test_blocage_apres_les_essais_autorises(self):
        limiteur = Limiteur(maxi=3, fenetre_s=60)
        for _ in range(2):
            limiteur.echec("a", maintenant=0)
        self.assertFalse(limiteur.bloque("a", maintenant=1))
        limiteur.echec("a", maintenant=1)
        self.assertTrue(limiteur.bloque("a", maintenant=2))

    def test_le_blocage_se_leve_avec_le_temps(self):
        limiteur = Limiteur(maxi=1, fenetre_s=60)
        limiteur.echec("a", maintenant=0)
        self.assertTrue(limiteur.bloque("a", maintenant=59))
        self.assertFalse(limiteur.bloque("a", maintenant=61))

    def test_une_connexion_reussie_efface_les_echecs(self):
        limiteur = Limiteur(maxi=1, fenetre_s=60)
        limiteur.echec("a", maintenant=0)
        limiteur.succes("a")
        self.assertFalse(limiteur.bloque("a", maintenant=1))

    def test_les_cles_sont_independantes(self):
        limiteur = Limiteur(maxi=1, fenetre_s=60)
        limiteur.echec("a", maintenant=0)
        self.assertFalse(limiteur.bloque("b", maintenant=1))


if __name__ == "__main__":
    unittest.main()
