import time
import unittest

from backend.services import travaux


def attendre(identifiant, delai=3.0):
    fin = time.time() + delai
    while time.time() < fin:
        etat = travaux.lire(identifiant)
        if etat["fini"]:
            return etat
        time.sleep(0.01)
    raise AssertionError("travail non terminé")


class TestTravaux(unittest.TestCase):
    def test_etapes_puis_resultat(self):
        vues = []

        def travail(progression):
            for etape in ("lancement_excel", "sauvegarde"):
                progression(etape)
                vues.append(etape)
            return 200, {"ok": True, "ligne": 12}

        ident = travaux.lancer(travail)
        etat = attendre(ident)
        self.assertEqual(vues, ["lancement_excel", "sauvegarde"])
        self.assertEqual((etat["statut"], etat["corps"]["ligne"], etat["etape"]), (200, 12, "termine"))

    def test_une_exception_donne_une_erreur_500(self):
        def travail(progression):
            raise RuntimeError("boum")

        etat = attendre(travaux.lancer(travail))
        self.assertEqual(etat["statut"], 500)
        self.assertIn("boum", etat["corps"]["erreurs"][0])

    def test_travail_inconnu(self):
        self.assertIsNone(travaux.lire("nexistepas"))

    def test_premiere_etape_est_l_attente(self):
        arret = []

        def travail(progression):
            while not arret:
                time.sleep(0.01)
            return 200, {}

        ident = travaux.lancer(travail)
        self.assertEqual(travaux.lire(ident)["etape"], "attente")
        self.assertFalse(travaux.lire(ident)["fini"])
        arret.append(1)
        attendre(ident)


if __name__ == "__main__":
    unittest.main()
