import unittest

from backend.services import reglages
from tests.utilitaires import BaseTest


class TestReglages(BaseTest):
    def test_valeurs_d_origine(self):
        configuration = reglages.config()
        self.assertEqual(configuration["seuil_demontee_avant_usure_mm"], 2)
        self.assertEqual(configuration["prix_meule_moyenne_eur"], 150)
        self.assertTrue(all(configuration["regles"].values()))
        vitesse = next(champ for champ in configuration["champs"] if champ["nom"] == "Vitesse de rotation")
        self.assertEqual(vitesse["max"], 50)

    def test_enregistrer_change_la_configuration(self):
        erreurs = reglages.enregistrer({"non_fini": {"actif": True, "params": {"seuil": 5}},
                                        "rotation_max": {"actif": True, "params": {"valeur": 40}}}, "alice")
        self.assertEqual(erreurs, [])
        configuration = reglages.config()
        self.assertEqual(configuration["seuil_demontee_avant_usure_mm"], 5)
        self.assertEqual(next(champ for champ in configuration["champs"] if champ["nom"] == "Vitesse de rotation")["max"], 40)

    def test_un_interrupteur_coupe_la_limite(self):
        reglages.enregistrer({"avance_max": {"actif": False, "params": {"valeur": 1000}}}, "alice")
        configuration = reglages.config()
        self.assertFalse(configuration["regles"]["avance_max"])
        self.assertNotIn("max", next(champ for champ in configuration["champs"] if champ["nom"] == "V.Avance"))

    def test_couper_hors_habitude_vide_la_liste_des_champs_controles(self):
        reglages.enregistrer({"hors_habitude": {"actif": False, "params": {}}}, "alice")
        self.assertEqual(reglages.config()["controle_habituel"]["champs"], [])

    def test_couper_machine_non_prevue(self):
        reglages.enregistrer({"machine_non_prevue": {"actif": False}}, "alice")
        machine = next(champ for champ in reglages.config()["champs"] if champ["nom"] == "N° de Machine")
        self.assertEqual(machine["hors_liste"], "ignorer")

    def test_valeurs_refusees(self):
        for valeur in ("abc", "", -5, 10 ** 9, True, None):
            erreurs = reglages.enregistrer({"rotation_max": {"actif": True, "params": {"valeur": valeur}}}, "alice")
            self.assertTrue(erreurs, msg=repr(valeur))
        self.assertEqual(reglages.etat()["modifie"], False)      # rien n'a été enregistré

    def test_regle_inconnue(self):
        self.assertTrue(reglages.enregistrer({"n_importe_quoi": {"actif": True}}, "alice"))

    def test_virgule_decimale_acceptee(self):
        reglages.enregistrer({"non_fini": {"actif": True, "params": {"seuil": "2,5"}}}, "alice")
        self.assertEqual(reglages.config()["seuil_demontee_avant_usure_mm"], 2.5)

    def test_historique(self):
        reglages.enregistrer({"non_fini": {"actif": False, "params": {"seuil": 2}}}, "alice")
        historique = reglages.historique()
        self.assertEqual(len(historique), 1)
        self.assertEqual((historique[0]["utilisateur"], historique[0]["avant"], historique[0]["apres"]),
                         ("alice", "actif · seuil=2", "désactivé · seuil=2"))

    def test_rien_a_noter_si_rien_ne_change(self):
        reglages.enregistrer({"non_fini": {"actif": True, "params": {"seuil": 2}}}, "alice")
        self.assertEqual(reglages.historique(), [])

    def test_reinitialiser(self):
        reglages.enregistrer({"non_fini": {"actif": True, "params": {"seuil": 9}}}, "alice")
        reglages.reinitialiser("bob")
        self.assertEqual(reglages.config()["seuil_demontee_avant_usure_mm"], 2)
        self.assertEqual(reglages.historique()[0]["utilisateur"], "bob")

    def test_etat_pour_la_page(self):
        etat = reglages.etat()
        ids = [regle["id"] for regle in etat["regles"]]
        self.assertIn("non_fini", ids)
        non_fini = next(regle for regle in etat["regles"] if regle["id"] == "non_fini")
        self.assertEqual(non_fini["params"][0]["valeur"], 2)


class TestAffichage(BaseTest):
    def test_humour_coupe_par_defaut(self):
        self.assertFalse(reglages.affichage()["humour"])

    def test_activer_puis_couper_et_historique(self):
        reglages.definir_humour(True, "alice")
        self.assertTrue(reglages.affichage()["humour"])
        reglages.definir_humour(True, "alice")                 # inchangé : rien de nouveau dans l'historique
        reglages.definir_humour(False, "bob")
        self.assertFalse(reglages.affichage()["humour"])
        changements = [ligne for ligne in reglages.historique() if "humoristiques" in ligne["regle"]]
        self.assertEqual([(ligne["utilisateur"], ligne["avant"], ligne["apres"]) for ligne in changements],
                         [("bob", "oui", "non"), ("alice", "non", "oui")])


if __name__ == "__main__":
    unittest.main()
