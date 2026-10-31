"""La construction de la démo en ligne est reproductible et son mode --check dit si docs/ est à jour.
Les tests travaillent dans un dossier temporaire, jamais dans la démo versionnée."""
import contextlib
import datetime
import io
import os
import shutil
import tempfile
import types
import unittest
from unittest import mock

from backend import config
from backend.services import controle, regles
from outils import construire_demo_web, donnees_fictives


class _AutreJour(datetime.date):
    """Une horloge en avance de 100 jours, pour simuler une construction faite un autre jour."""
    @classmethod
    def today(cls):
        return datetime.date.today() + datetime.timedelta(days=100)


@contextlib.contextmanager
def _horloge_decalee():
    """Décale la date du jour partout où la construction de la démo pourrait la lire."""
    module_decale = types.SimpleNamespace(**{**vars(datetime), "date": _AutreJour})
    with contextlib.ExitStack() as pile:
        for module in (donnees_fictives, regles, controle):
            pile.enter_context(mock.patch.object(module, "datetime", module_decale))
        yield


def _instantane_des_fichiers(dossier):
    """Date de modification de chaque fichier du dossier, pour vérifier que rien n'a été écrit."""
    return {os.path.join(racine, nom): os.stat(os.path.join(racine, nom)).st_mtime_ns
            for racine, _, noms in os.walk(dossier) for nom in noms}


class TestConstructionDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        anciens = (config.DB_PATH, config.FICHIER)
        cls.addClassCleanup(setattr, config, "FICHIER", anciens[1])
        cls.addClassCleanup(setattr, config, "DB_PATH", anciens[0])
        temporaire = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporaire.cleanup)
        cls.reference = os.path.join(temporaire.name, "reference")
        construire_demo_web.construire(cls.reference)

    def setUp(self):
        temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(temporaire.cleanup)
        self.sortie = os.path.join(temporaire.name, "docs")
        shutil.copytree(self.reference, self.sortie)

    def verifier(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as affichage:
            code = construire_demo_web.main(["--check"], sortie=self.sortie)
        return code, affichage.getvalue()

    def test_une_construction_faite_un_autre_jour_donne_les_memes_fichiers(self):
        with _horloge_decalee():
            self.assertEqual(construire_demo_web.ecarts(self.reference), [])

    def test_check_sur_une_demo_fraiche_repond_a_jour(self):
        code, message = self.verifier()
        self.assertEqual(code, 0)
        self.assertIn("à jour", message)

    def test_check_cite_les_fichiers_modifies_en_trop_et_manquants(self):
        with open(os.path.join(self.sortie, "index.html"), "a", encoding="utf-8") as fichier:
            fichier.write("<!-- modifié à la main -->")
        open(os.path.join(self.sortie, "oublie.txt"), "w").close()
        os.remove(os.path.join(self.sortie, "static", "js", "admin.js"))
        code, message = self.verifier()
        self.assertEqual(code, 1)
        self.assertIn("modifié : index.html", message)
        self.assertIn("en trop : oublie.txt", message)
        self.assertIn(f"manquant : {os.path.join('static', 'js', 'admin.js')}", message)
        self.assertNotIn("demo_data.json", message)

    def test_les_fins_de_ligne_windows_ne_comptent_pas_comme_une_modification(self):
        chemin = os.path.join(self.sortie, "index.html")
        with open(chemin, "rb") as fichier:
            contenu = fichier.read()
        with open(chemin, "wb") as fichier:
            fichier.write(contenu.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(self.verifier()[0], 0)

    def test_les_dossiers_ecrits_a_la_main_sont_ignores_et_preserves(self):
        for dossier in ("agents", "adr"):
            os.makedirs(os.path.join(self.sortie, dossier))
            with open(os.path.join(self.sortie, dossier, "note.md"), "w", encoding="utf-8") as fichier:
                fichier.write("écrit à la main")
        code, message = self.verifier()
        self.assertEqual((code, "note.md" in message), (0, False))
        construire_demo_web.construire(self.sortie)
        self.assertTrue(os.path.isfile(os.path.join(self.sortie, "agents", "note.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.sortie, "adr", "note.md")))

    def test_check_n_ecrit_rien(self):
        os.remove(os.path.join(self.sortie, "demo_data.json"))
        with open(os.path.join(self.sortie, "index.html"), "w", encoding="utf-8") as fichier:
            fichier.write("ancienne page")
        avant = _instantane_des_fichiers(self.sortie)
        self.verifier()
        self.assertEqual(_instantane_des_fichiers(self.sortie), avant)
        with open(os.path.join(self.sortie, "index.html"), encoding="utf-8") as fichier:
            self.assertEqual(fichier.read(), "ancienne page")
        self.assertFalse(os.path.exists(os.path.join(self.sortie, "demo_data.json")))

    def test_un_argument_inconnu_est_refuse_sans_reconstruire(self):
        avant = _instantane_des_fichiers(self.sortie)
        with self.assertRaises(SystemExit) as sortie, mock.patch("sys.stderr", new_callable=io.StringIO):
            construire_demo_web.main(["--chek"], sortie=self.sortie)
        self.assertNotEqual(sortie.exception.code, 0)
        self.assertEqual(_instantane_des_fichiers(self.sortie), avant)


if __name__ == "__main__":
    unittest.main()
