import datetime
import unittest

from backend.services import controle
from tests.utilitaires import BaseTest, ligne_data

NORMALES = [ligne_data(**{"Nb faces/meule de 89 mm": 1500 + rang * 10, "Compteur fin": 1500 + rang * 10,
                          "Date montage": datetime.datetime(2025, 1, 1 + rang)}) for rang in range(10)]


def anomalies_de(ligne_xl):
    return [anomalie for anomalie in controle.anomalies()["anomalies"] if anomalie["ligne"] == ligne_xl]


class TestControleQualite(BaseTest):
    lignes = NORMALES + [
        ligne_data(**{"Compteur fin": 0, "Date montage": datetime.datetime(2025, 3, 1)}),                # ligne 12
        ligne_data(**{"Vitesse de rotation": 500, "Date montage": datetime.datetime(2025, 3, 2)}),       # ligne 13
        ligne_data(**{"Nb faces/meule de 89 mm": 90000, "Date montage": datetime.datetime(2025, 3, 3)}), # ligne 14
        ligne_data(**{"Date montage": "pas une date"}),                                                  # ligne 15
        ligne_data(**{"Matière": "Z", "Date montage": datetime.datetime(2025, 3, 5)}),                   # ligne 16
    ]

    def test_les_lignes_normales_ne_sont_pas_signalees(self):
        for numero_ligne in range(2, 12):
            self.assertEqual(anomalies_de(numero_ligne), [], msg=f"ligne {numero_ligne}")

    def test_compteur_fin_a_zero(self):
        self.assertTrue(any("0" in anomalie["motif"] and anomalie["colonne"] == "Compteur fin" for anomalie in anomalies_de(12)))

    def test_limite_depassee(self):
        self.assertTrue(any(anomalie["colonne"] == "Vitesse de rotation" and anomalie["gravite"] == controle.GRAVE for anomalie in anomalies_de(13)))

    def test_duree_de_vie_tres_eloignee(self):
        self.assertTrue(any("éloigné" in anomalie["motif"] for anomalie in anomalies_de(14)))

    def test_date_en_texte(self):
        self.assertTrue(any(anomalie["colonne"] == "Date montage" for anomalie in anomalies_de(15)))

    def test_matiere_inconnue(self):
        self.assertTrue(any(anomalie["colonne"] == "Matière" for anomalie in anomalies_de(16)))

    def test_les_graves_sont_classes_en_premier(self):
        gravites = [anomalie["gravite"] for anomalie in controle.anomalies()["anomalies"]]
        self.assertEqual(gravites, sorted(gravites, key=lambda gravite: controle.ORDRE[gravite]))

    def test_le_controle_des_durees_de_vie_peut_etre_coupe(self):
        from backend.services import reglages
        reglages.enregistrer({"controle_eloigne": {"actif": False, "params": {"coefficient": 3}}}, "t")
        self.assertFalse(any("éloigné" in anomalie["motif"] for anomalie in anomalies_de(14)))


class TestDoublons(BaseTest):
    lignes = [ligne_data(), ligne_data(), ligne_data(**{"Face": "B"})]

    def test_lignes_identiques(self):
        identiques = [anomalie for anomalie in controle.anomalies()["anomalies"] if "identiques" in anomalie["motif"]]
        self.assertEqual([anomalie["ligne"] for anomalie in identiques], [3])           # la 2e ligne copie la 1re ; la 3e est différente


if __name__ == "__main__":
    unittest.main()
