import unittest

from backend.auth import utilisateurs
from backend.auth.utilisateurs import ErreurUtilisateur
from tests.utilitaires import BaseTest


class TestUtilisateurs(BaseTest):
    def test_creer_et_authentifier(self):
        uid = utilisateurs.creer("alice", "motdepasse1")
        compte = utilisateurs.authentifier("alice", "motdepasse1")
        self.assertEqual(compte["id"], uid)
        self.assertIsNone(utilisateurs.authentifier("alice", "faux"))
        self.assertIsNone(utilisateurs.authentifier("inconnu", "motdepasse1"))

    def test_le_nom_ne_depend_pas_de_la_casse(self):
        utilisateurs.creer("Alice", "motdepasse1")
        self.assertIsNotNone(utilisateurs.authentifier("alice", "motdepasse1"))
        with self.assertRaises(ErreurUtilisateur):
            utilisateurs.creer("ALICE", "motdepasse1")

    def test_nom_invalide(self):
        for nom in ("ab", "a" * 33, "avec espace", "é-accent", "", None, "x;drop"):
            with self.assertRaises(ErreurUtilisateur, msg=repr(nom)):
                utilisateurs.creer(nom, "motdepasse1")

    def test_mot_de_passe_trop_court(self):
        with self.assertRaises(ErreurUtilisateur):
            utilisateurs.creer("alice", "court")
        self.assertEqual(utilisateurs.nombre(), 0)

    def test_la_liste_ne_contient_jamais_de_mot_de_passe(self):
        utilisateurs.creer("alice", "motdepasse1")
        for compte in utilisateurs.lister():
            self.assertNotIn("mdp_hash", compte)
            self.assertNotIn("motdepasse1", str(compte))

    def test_supprimer(self):
        alice = utilisateurs.creer("alice", "motdepasse1")
        bob = utilisateurs.creer("bob", "motdepasse2")
        with self.assertRaises(ErreurUtilisateur):
            utilisateurs.supprimer(alice, par_id=alice)            # pas son propre compte
        utilisateurs.supprimer(bob, par_id=alice)
        self.assertEqual(utilisateurs.nombre(), 1)

    def test_le_dernier_compte_ne_se_supprime_pas(self):
        alice = utilisateurs.creer("alice", "motdepasse1")
        with self.assertRaises(ErreurUtilisateur):
            utilisateurs.supprimer(alice, par_id=999)
        self.assertEqual(utilisateurs.nombre(), 1)

    def test_supprimer_un_compte_inexistant(self):
        alice = utilisateurs.creer("alice", "motdepasse1")
        utilisateurs.creer("bob", "motdepasse2")
        with self.assertRaises(ErreurUtilisateur):
            utilisateurs.supprimer(12345, par_id=alice)

    def test_changer_mon_mot_de_passe(self):
        alice = utilisateurs.creer("alice", "motdepasse1")
        with self.assertRaises(ErreurUtilisateur):
            utilisateurs.changer_mon_mot_de_passe(alice, "mauvais", "nouveaumdp1")
        utilisateurs.changer_mon_mot_de_passe(alice, "motdepasse1", "nouveaumdp1")
        self.assertIsNone(utilisateurs.authentifier("alice", "motdepasse1"))
        self.assertIsNotNone(utilisateurs.authentifier("alice", "nouveaumdp1"))

    def test_changer_mon_nom(self):
        alice = utilisateurs.creer("alice", "motdepasse1")
        utilisateurs.creer("bob", "motdepasse2")
        with self.assertRaises(ErreurUtilisateur):
            utilisateurs.changer_mon_nom(alice, "carole", "faux")           # mot de passe faux
        with self.assertRaises(ErreurUtilisateur):
            utilisateurs.changer_mon_nom(alice, "bob", "motdepasse1")       # nom pris
        utilisateurs.changer_mon_nom(alice, "carole", "motdepasse1")
        self.assertEqual(utilisateurs.trouver(alice)["nom"], "carole")
        utilisateurs.changer_mon_nom(alice, "CAROLE", "motdepasse1")        # changer la casse de son propre nom est permis

    def test_session_valide(self):
        utilisateurs.creer("alice", "motdepasse1")
        compte = utilisateurs.authentifier("alice", "motdepasse1")
        jeton = utilisateurs.ouvrir_session(compte)
        self.assertEqual(utilisateurs.utilisateur_de_session(jeton)["nom"], "alice")
        self.assertIsNone(utilisateurs.utilisateur_de_session("n'importe quoi"))
        self.assertIsNone(utilisateurs.utilisateur_de_session(None))

    def test_un_nouveau_mot_de_passe_ferme_les_sessions(self):
        alice = utilisateurs.creer("alice", "motdepasse1")
        jeton = utilisateurs.ouvrir_session(utilisateurs.authentifier("alice", "motdepasse1"))
        utilisateurs.reinitialiser_mot_de_passe(alice, "motdepasse2")
        self.assertIsNone(utilisateurs.utilisateur_de_session(jeton))

    def test_une_session_disparait_avec_le_compte(self):
        alice = utilisateurs.creer("alice", "motdepasse1")
        bob = utilisateurs.creer("bob", "motdepasse2")
        jeton = utilisateurs.ouvrir_session(utilisateurs.authentifier("bob", "motdepasse2"))
        utilisateurs.supprimer(bob, par_id=alice)
        self.assertIsNone(utilisateurs.utilisateur_de_session(jeton))


if __name__ == "__main__":
    unittest.main()
