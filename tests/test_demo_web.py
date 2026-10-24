"""La démo en ligne (JavaScript) doit donner les mêmes verdicts que le vrai code Python.
Ce test est ignoré si Node.js n'est pas installé."""
import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest

from backend import config
from backend.services import donnees, listes, reglages
from backend.services.regles import traiter
from outils import construire_demo_web
from outils.donnees_fictives import creer_classeur

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(shutil.which("node"), "Node.js absent")
class TestParite(unittest.TestCase):
    def test_memes_verdicts_que_python(self):
        with tempfile.TemporaryDirectory() as dossier:
            anciens = (config.DB_PATH, config.FICHIER)
            try:
                instantane = construire_demo_web.instantane(dossier)      # configure aussi config.DB_PATH / FICHIER
                for cache in (donnees._cache, donnees._cache_t, listes._cache):
                    cache["mtime"] = None
                reglages._cache.update(cle=None, config=None)
                table = donnees.tableau()
                champs = reglages.config()["champs"]
                aleatoire = random.Random(3)
                saisies = []
                for ligne in aleatoire.sample(table["lignes"], 40):
                    ligne_dict = dict(zip(table["cles"], ligne[1:]))
                    saisie = {champ["nom"]: ligne_dict.get(donnees.norm(champ["nom"])) for champ in champs}
                    saisie["Commentaire"] = saisie.get("Commentaire") or ""
                    saisies.append(saisie)
                    abime = dict(saisie)
                    cle = aleatoire.choice(["Vitesse de rotation", "V.Avance", "Compteur fin", "Pression d'arrosage", "Hauteur meule initiale, mm"])
                    abime[cle] = (abime[cle] or 0) * aleatoire.choice([0, 3, 10, 0.1])
                    abime["Matricule monteur"] = aleatoire.choice(["12", "9999", "abcd", abime["Matricule monteur"]])
                    abime["Hauteur meule finale, mm"] = aleatoire.choice([0, 5, 200, abime["Hauteur meule finale, mm"]])
                    abime["Date montage"] = aleatoire.choice([abime["Date montage"], "2030-01-01", "31/02/2026"])
                    saisies.append(abime)
                attendu = []
                for saisie in saisies:
                    _, erreurs, avertissements = traiter(saisie)
                    attendu.append({"erreurs": erreurs, "avertissements": avertissements})
                fichier_demo = os.path.join(dossier, "demo.json")
                fichier_saisies = os.path.join(dossier, "saisies.json")
                with open(fichier_demo, "w", encoding="utf-8") as f:
                    json.dump(instantane, f, ensure_ascii=False)
                with open(fichier_saisies, "w", encoding="utf-8") as f:
                    json.dump(saisies, f, ensure_ascii=False, default=str)
                sortie = subprocess.run(["node", os.path.join(RACINE, "tests", "parite_demo_web.js"), fichier_demo, fichier_saisies],
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(sortie.returncode, 0, sortie.stderr)
                obtenu = json.loads(sortie.stdout)
                self.assertEqual(len(obtenu), len(attendu))
                differences = [(i, a, o) for i, (a, o) in enumerate(zip(attendu, obtenu)) if a != o]
                self.assertEqual(differences[:3], [])
                self.assertTrue(any(a["avertissements"] for a in attendu) and any(a["erreurs"] for a in attendu))
            finally:
                config.DB_PATH, config.FICHIER = anciens


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("node"), "Node.js absent")
class TestDecalageDesDates(unittest.TestCase):
    def test_les_dates_suivent_le_jour_d_ouverture(self):
        import datetime
        with tempfile.TemporaryDirectory() as dossier:
            anciens = (config.DB_PATH, config.FICHIER)
            try:
                instantane = construire_demo_web.instantane(dossier)
            finally:
                config.DB_PATH, config.FICHIER = anciens
            colonne = instantane["donnees"]["entetes"].index("Date montage") + 1
            originales = [ligne[colonne] for ligne in instantane["donnees"]["lignes"]]
            instantane["date_construction"] = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
            fichier = os.path.join(dossier, "demo.json")
            with open(fichier, "w", encoding="utf-8") as f:
                json.dump(instantane, f, ensure_ascii=False)
            sortie = subprocess.run(["node", os.path.join(RACINE, "tests", "decalage_demo_web.js"), fichier],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(sortie.returncode, 0, sortie.stderr)
            vues = json.loads(sortie.stdout)
            attendues = [(datetime.date.fromisoformat(d) + datetime.timedelta(days=10)).isoformat() if isinstance(d, str) and len(d) == 10 and d[4] == "-" else d
                         for d in originales]
            self.assertEqual(vues, attendues)
            self.assertNotEqual(vues, originales)
