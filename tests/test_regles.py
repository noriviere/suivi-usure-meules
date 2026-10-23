import datetime
import unittest

from backend.services import regles, reglages
from tests.utilitaires import BaseTest, ligne_data

# 30 meules habituelles : vitesse 30 à 34 m/s, compteur fin 1400 à 1600
HISTORIQUE = [ligne_data(**{"Vitesse de rotation": 30 + rang % 5, "Compteur fin": 1400 + (rang % 5) * 50,
                            "Date montage": datetime.datetime(2025, 1, 1 + rang % 28)}) for rang in range(30)]

SAISIE = {"Matricule monteur": "0123", "Format": "8", "Matière": "I", "Face": "A", "N° article meule": "0105",
          "Lot fournisseur N° FA / Beleg": "123", "Date montage": "2026-10-01", "N° de Machine": "s7",
          "Pression d'arrosage": 6, "Vitesse de rotation": 32, "V.Avance": 850, "Hauteur meule initiale, mm": 89,
          "Compteur début": 0, "Matricule démonteur": "0123", "Compteur fin": 1500, "Hauteur meule finale, mm": 0}


class TestTraiter(BaseTest):
    lignes = HISTORIQUE

    def test_saisie_normale(self):
        propres, erreurs, avertissements = regles.traiter(SAISIE)
        self.assertEqual((erreurs, avertissements), ([], []))
        self.assertEqual(propres["MA5"], "Non")                    # déduit du tableau Formats & matière

    def test_matricule_court_complete(self):
        propres, erreurs, _ = regles.traiter({**SAISIE, "Matricule monteur": "123"})
        self.assertEqual(erreurs, [])
        self.assertEqual(propres["Matricule monteur"], "0123")

    def test_combinaison_format_matiere_inconnue(self):
        _, erreurs, _ = regles.traiter({**SAISIE, "Matière": "C", "Format": "9"})
        self.assertTrue(any("combinaison" in erreur for erreur in erreurs))

    def test_ma5_peut_etre_oblige_de_choisir(self):
        _, erreurs, _ = regles.traiter({**SAISIE, "Matière": "C", "N° de Machine": "s1"})
        self.assertTrue(any("MA5" in erreur for erreur in erreurs))
        propres, erreurs, _ = regles.traiter({**SAISIE, "Matière": "C", "N° de Machine": "s1", "MA5": "oui"})
        self.assertEqual(erreurs, [])
        self.assertEqual(propres["MA5"], "Oui")

    def test_compteur_fin_zero_devient_un(self):
        propres, erreurs, avertissements = regles.traiter({**SAISIE, "Compteur fin": 0})
        self.assertEqual(propres["Compteur fin"], 1)
        self.assertTrue(any("remplacé par 1" in avertissement for avertissement in avertissements))
        self.assertEqual(erreurs, [])

    def test_meule_non_finie_exige_un_commentaire(self):
        _, erreurs, _ = regles.traiter({**SAISIE, "Hauteur meule finale, mm": 5})
        self.assertTrue(any("Commentaire obligatoire" in erreur for erreur in erreurs))
        _, erreurs, _ = regles.traiter({**SAISIE, "Hauteur meule finale, mm": 5, "Commentaire": "Meule cassée"})
        self.assertEqual(erreurs, [])

    def test_seuil_de_meule_non_finie(self):
        _, erreurs, _ = regles.traiter({**SAISIE, "Hauteur meule finale, mm": 2})     # 2 mm : pas au-dessus du seuil
        self.assertEqual(erreurs, [])

    def test_commentaire_non_exige_si_regle_coupee(self):
        reglages.enregistrer({"non_fini": {"actif": False, "params": {"seuil": 2}}}, "t")
        _, erreurs, _ = regles.traiter({**SAISIE, "Hauteur meule finale, mm": 5})
        self.assertEqual(erreurs, [])

    def test_seuil_modifie(self):
        reglages.enregistrer({"non_fini": {"actif": True, "params": {"seuil": 10}}}, "t")
        _, erreurs, _ = regles.traiter({**SAISIE, "Hauteur meule finale, mm": 5})
        self.assertEqual(erreurs, [])

    def test_valeur_hors_habitude(self):
        _, erreurs, avertissements = regles.traiter({**SAISIE, "Vitesse de rotation": 48})
        self.assertEqual(erreurs, [])
        self.assertTrue(any("Vitesse de rotation" in avertissement and "inhabituel" in avertissement for avertissement in avertissements))

    def test_hors_habitude_desactive(self):
        reglages.enregistrer({"hors_habitude": {"actif": False, "params": {}}}, "t")
        _, _, avertissements = regles.traiter({**SAISIE, "Vitesse de rotation": 48})
        self.assertFalse(any("inhabituel" in avertissement for avertissement in avertissements))

    def test_pression_zero_est_normale(self):
        _, _, avertissements = regles.traiter({**SAISIE, "Pression d'arrosage": 0})
        self.assertFalse(any("Pression" in avertissement for avertissement in avertissements))

    def test_pas_assez_d_historique_pas_d_avertissement(self):
        # le compteur fin d'une meule jamais vue n'est pas comparé
        _, _, avertissements = regles.traiter({**SAISIE, "N° article meule": "0999", "Compteur fin": 99999})
        self.assertFalse(any("Compteur fin" in avertissement for avertissement in avertissements))

    def test_meule_differente_de_celle_prevue(self):
        _, erreurs, avertissements = regles.traiter({**SAISIE, "N° article meule": "0999"})
        self.assertEqual(erreurs, [])
        self.assertTrue(any("meule prévue" in avertissement for avertissement in avertissements))
        reglages.enregistrer({"meule_non_prevue": {"actif": False}}, "t")
        self.assertFalse(any("meule prévue" in avertissement for avertissement in regles.traiter({**SAISIE, "N° article meule": "0999"})[2]))

    def test_matricule_jamais_vu(self):
        _, _, avertissements = regles.traiter({**SAISIE, "Matricule monteur": "9999"})
        self.assertTrue(any("9999" in avertissement and "jamais" in avertissement for avertissement in avertissements))
        reglages.enregistrer({"matricule_inconnu": {"actif": False}}, "t")
        self.assertFalse(any("jamais" in avertissement for avertissement in regles.traiter({**SAISIE, "Matricule monteur": "9999"})[2]))

    def test_doublon(self):
        existante = dict(SAISIE, **{"Date montage": "2025-01-01", "Compteur fin": 1400, "Face": "A"})
        _, _, avertissements = regles.traiter(existante)
        self.assertTrue(any("identique" in avertissement for avertissement in avertissements))
        reglages.enregistrer({"doublon_saisie": {"actif": False}}, "t")
        self.assertFalse(any("identique" in avertissement for avertissement in regles.traiter(existante)[2]))


class TestAutresFonctions(BaseTest):
    lignes = HISTORIQUE

    def test_vers_defaut(self):
        base = {"Hauteur meule finale, mm": 5, "Commentaire": "Meule cassée ou fissurée : fissure"}
        self.assertTrue(regles.vers_defaut(base))
        self.assertFalse(regles.vers_defaut({**base, "Hauteur meule finale, mm": 1}))      # sous le seuil
        self.assertFalse(regles.vers_defaut({**base, "Commentaire": "Bruit"}))
        self.assertFalse(regles.vers_defaut({"Commentaire": "Meule cassée ou fissurée"}))

    def test_verifier_champ(self):
        self.assertIn("inhabituel", regles.verifier_champ("Vitesse de rotation", "60"))
        self.assertEqual(regles.verifier_champ("Vitesse de rotation", "32"), "")
        self.assertEqual(regles.verifier_champ("Vitesse de rotation", "abc"), "")
        self.assertEqual(regles.verifier_champ("Vitesse de rotation", ""), "")
        self.assertEqual(regles.verifier_champ("Face", "60"), "")                         # champ non contrôlé
        self.assertEqual(regles.verifier_champ("Vitesse de rotation", "12,5").startswith("Vitesse"), True)

    def test_perte_annuelle(self):
        perte = regles.perte_annuelle(annee=2025)
        self.assertEqual(perte["nb"], 0)                                                       # toutes finies à 0 mm
        self.assertEqual(perte["prix"], 150)


class TestPerte(BaseTest):
    lignes = [ligne_data(**{"Hauteur meule finale, mm": 8.9, "Date montage": datetime.datetime(2026, 3, 1)}),
              ligne_data(**{"Hauteur meule finale, mm": 0, "Date montage": datetime.datetime(2026, 3, 2)}),
              ligne_data(**{"Hauteur meule finale, mm": 44.5, "Date montage": datetime.datetime(2025, 3, 2)})]

    def test_la_perte_est_proportionnelle_a_la_hauteur_restante(self):
        perte = regles.perte_annuelle(annee=2026)
        self.assertEqual(perte["nb"], 1)                       # la meule finie à 0 mm ne compte pas
        self.assertAlmostEqual(perte["total"], 15.0)           # 8,9 / 89 x 150 €

    def test_le_prix_vient_des_regles(self):
        reglages.enregistrer({"prix_meule": {"params": {"valeur": 200}}}, "t")
        self.assertAlmostEqual(regles.perte_annuelle(annee=2026)["total"], 20.0)


if __name__ == "__main__":
    unittest.main()
