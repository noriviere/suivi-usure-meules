import datetime
import unittest

from backend.services import reglages
from backend.services.valider import valider
from tests.utilitaires import BaseTest

COMPLET = {"Matricule monteur": "0123", "Format": "8", "Matière": "I", "Face": "A", "N° article meule": "0105",
           "Lot fournisseur N° FA / Beleg": "123", "Date montage": "2026-05-04", "N° de Machine": "s7", "MA5": "Non",
           "Pression d'arrosage": 6, "Vitesse de rotation": 32, "V.Avance": 850, "Hauteur meule initiale, mm": 89,
           "Compteur début": 0, "Matricule démonteur": "0123", "Compteur fin": 1500, "Hauteur meule finale, mm": 0}
LISTES = {"Format": ["8"], "Matière": ["I", "C"], "N° article meule": ["0105"], "N° de Machine": ["s1", "s7"]}


def erreurs_de(**modifs):
    donnees = {**COMPLET, **modifs}
    return valider(donnees, LISTES)[1]


class TestValider(BaseTest):
    def test_saisie_complete_sans_erreur(self):
        propres, erreurs, avertissements = valider(COMPLET, LISTES)
        self.assertEqual((erreurs, avertissements), ([], []))
        self.assertEqual(propres["Compteur fin"], 1500)
        self.assertEqual(propres["Date montage"], datetime.datetime(2026, 5, 4))

    def test_champ_obligatoire_manquant(self):
        self.assertTrue(any("Face" in erreur for erreur in erreurs_de(Face="")))
        self.assertTrue(any("Face" in erreur for erreur in erreurs_de(Face=None)))

    def test_nombres_avec_virgule_ou_texte(self):
        self.assertEqual(erreurs_de(**{"Hauteur meule initiale, mm": "89,5"}), [])
        self.assertTrue(erreurs_de(**{"Vitesse de rotation": "abc"}))
        self.assertTrue(erreurs_de(**{"Vitesse de rotation": "nan"}))
        self.assertTrue(erreurs_de(**{"Vitesse de rotation": "inf"}))
        self.assertTrue(erreurs_de(**{"Vitesse de rotation": True}))

    def test_un_entier_refuse_les_decimales(self):
        self.assertTrue(erreurs_de(**{"V.Avance": 850.5}))
        self.assertEqual(erreurs_de(**{"V.Avance": 850.0}), [])

    def test_limites(self):
        self.assertEqual(erreurs_de(**{"Vitesse de rotation": 50}), [])
        self.assertTrue(erreurs_de(**{"Vitesse de rotation": 51}))
        self.assertTrue(erreurs_de(**{"Vitesse de rotation": -1}))
        self.assertTrue(erreurs_de(**{"V.Avance": 1001}))
        self.assertEqual(erreurs_de(**{"Hauteur meule initiale, mm": 110}), [])
        self.assertTrue(erreurs_de(**{"Hauteur meule initiale, mm": 110.1}))

    def test_limite_modifiee_dans_les_regles(self):
        reglages.enregistrer({"rotation_max": {"actif": True, "params": {"valeur": 40}}}, "t")
        self.assertTrue(erreurs_de(**{"Vitesse de rotation": 45}))

    def test_limite_desactivee(self):
        reglages.enregistrer({"rotation_max": {"actif": False, "params": {"valeur": 50}}}, "t")
        self.assertEqual(erreurs_de(**{"Vitesse de rotation": 500}), [])

    def test_matricule_a_4_caracteres(self):
        self.assertTrue(erreurs_de(**{"Matricule monteur": "123"}))
        self.assertTrue(erreurs_de(**{"Matricule monteur": "01230"}))

    def test_date_invalide_ou_future(self):
        self.assertTrue(erreurs_de(**{"Date montage": "31/02/2026"}))
        self.assertTrue(erreurs_de(**{"Date montage": "2026-02-30"}))
        demain = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        propres, erreurs, avertissements = valider({**COMPLET, "Date montage": demain}, LISTES)
        self.assertEqual(erreurs, [])
        self.assertTrue(any("futur" in avertissement for avertissement in avertissements))

    def test_date_future_avertissement_desactive(self):
        reglages.enregistrer({"date_futur": {"actif": False}}, "t")
        demain = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(valider({**COMPLET, "Date montage": demain}, LISTES)[2], [])

    def test_valeur_hors_liste(self):
        self.assertTrue(erreurs_de(Format="999"))

    def test_machine_hors_liste_demande_un_commentaire(self):
        _, erreurs, avertissements = valider({**COMPLET, "N° de Machine": "s5"}, LISTES)
        self.assertTrue(any("Commentaire obligatoire" in erreur for erreur in erreurs))
        self.assertTrue(any("s5" in avertissement for avertissement in avertissements))
        _, erreurs, _ = valider({**COMPLET, "N° de Machine": "s5", "Commentaire": "Machine s7 en panne"}, LISTES)
        self.assertEqual(erreurs, [])

    def test_machine_hors_liste_acceptee_si_regle_coupee(self):
        reglages.enregistrer({"machine_non_prevue": {"actif": False}}, "t")
        _, erreurs, avertissements = valider({**COMPLET, "N° de Machine": "s5"}, LISTES)
        self.assertEqual((erreurs, avertissements), ([], []))

    def test_coherence_des_compteurs_et_des_hauteurs(self):
        self.assertTrue(any("Compteur fin" in erreur for erreur in erreurs_de(**{"Compteur début": 100, "Compteur fin": 50})))
        self.assertTrue(any("Hauteur finale" in erreur for erreur in erreurs_de(**{"Hauteur meule finale, mm": 90})))


if __name__ == "__main__":
    unittest.main()
