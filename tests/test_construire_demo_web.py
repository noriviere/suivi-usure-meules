"""La construction de la démo en ligne est reproductible et son mode --check dit si docs/ est à jour.
Les tests travaillent dans un dossier temporaire, jamais dans la démo versionnée."""
import datetime
import filecmp
import io
import os
import tempfile
import types
import unittest
from unittest import mock

from backend import config
from outils import construire_demo_web, donnees_fictives


class _AutreJour(datetime.date):
    """Une horloge qui avance de 100 jours, pour simuler une construction faite un autre jour."""
    @classmethod
    def today(cls):
        return datetime.date.today() + datetime.timedelta(days=100)


def _horloge_decalee():
    return mock.patch.object(donnees_fictives, "datetime", types.SimpleNamespace(**{**vars(datetime), "date": _AutreJour}))


class TestConstructionDemo(unittest.TestCase):
    def setUp(self):
        anciens = (config.DB_PATH, config.FICHIER)
        self.addCleanup(lambda: setattr(config, "DB_PATH", anciens[0]) or setattr(config, "FICHIER", anciens[1]))
        temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(temporaire.cleanup)
        self.dossier = temporaire.name

    def construire(self, nom):
        sortie = os.path.join(self.dossier, nom)
        construire_demo_web.construire(sortie)
        return sortie

    def test_deux_constructions_faites_des_jours_differents_donnent_les_memes_fichiers(self):
        premiere = self.construire("premiere")
        with _horloge_decalee():
            seconde = self.construire("seconde")
        comparaison = filecmp.dircmp(premiere, seconde)
        self.assertEqual((comparaison.left_only, comparaison.right_only), ([], []))
        fichiers = [os.path.relpath(os.path.join(racine, nom), premiere)
                    for racine, _, noms in os.walk(premiere) for nom in noms]
        _, differents, erreurs = filecmp.cmpfiles(premiere, seconde, fichiers, shallow=False)
        self.assertEqual((differents, erreurs), ([], []))
        self.assertIn("demo_data.json", fichiers)

    def verifier(self, sortie):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as affichage:
            code = construire_demo_web.main(["--check"], sortie=sortie)
        return code, affichage.getvalue()

    def test_check_sur_une_demo_fraiche_repond_a_jour(self):
        code, message = self.verifier(self.construire("docs"))
        self.assertEqual(code, 0)
        self.assertIn("à jour", message)

    def test_check_cite_les_fichiers_modifies_en_trop_et_manquants(self):
        sortie = self.construire("docs")
        with open(os.path.join(sortie, "index.html"), "a", encoding="utf-8") as fichier:
            fichier.write("<!-- modifié à la main -->")
        open(os.path.join(sortie, "oublie.txt"), "w").close()
        os.remove(os.path.join(sortie, "static", "js", "admin.js"))
        code, message = self.verifier(sortie)
        self.assertEqual(code, 1)
        self.assertIn("modifié : index.html", message)
        self.assertIn("en trop : oublie.txt", message)
        self.assertIn(f"manquant : {os.path.join('static', 'js', 'admin.js')}", message)
        self.assertNotIn("demo_data.json", message)

    def test_les_dossiers_ecrits_a_la_main_sont_ignores_et_preserves(self):
        sortie = self.construire("docs")
        for dossier in ("agents", "adr"):
            os.makedirs(os.path.join(sortie, dossier))
            with open(os.path.join(sortie, dossier, "note.md"), "w", encoding="utf-8") as fichier:
                fichier.write("écrit à la main")
        code, message = self.verifier(sortie)
        self.assertEqual((code, "note.md" in message), (0, False))
        construire_demo_web.construire(sortie)
        self.assertTrue(os.path.isfile(os.path.join(sortie, "agents", "note.md")))
        self.assertTrue(os.path.isfile(os.path.join(sortie, "adr", "note.md")))

    def test_check_n_ecrit_rien(self):
        sortie = self.construire("docs")
        os.remove(os.path.join(sortie, "demo_data.json"))
        with open(os.path.join(sortie, "index.html"), "w", encoding="utf-8") as fichier:
            fichier.write("ancienne page")
        avant = {nom: os.stat(os.path.join(racine, nom)).st_mtime_ns for racine, _, noms in os.walk(sortie) for nom in noms}
        self.verifier(sortie)
        apres = {nom: os.stat(os.path.join(racine, nom)).st_mtime_ns for racine, _, noms in os.walk(sortie) for nom in noms}
        self.assertEqual(apres, avant)
        with open(os.path.join(sortie, "index.html"), encoding="utf-8") as fichier:
            self.assertEqual(fichier.read(), "ancienne page")
        self.assertFalse(os.path.exists(os.path.join(sortie, "demo_data.json")))


if __name__ == "__main__":
    unittest.main()
