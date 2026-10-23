"""Cree un compte du back-office, ou change le mot de passe d'un compte existant (mot de passe oublie).
A lancer sur le PC serveur : scripts/creer_utilisateur.bat"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import utilisateurs                      # noqa: E402
from backend.auth.utilisateurs import ErreurUtilisateur    # noqa: E402


def main():
    print("Comptes existants :", ", ".join(compte["nom"] for compte in utilisateurs.lister()) or "(aucun)")
    nom = input("Nom d'utilisateur (nouveau, ou existant pour changer son mot de passe) : ").strip()
    print("Le mot de passe s'affiche pendant la frappe (rien n'est cache) : c'est normal ici.")
    mdp = input("Mot de passe (8 caracteres minimum) : ").strip()
    if input("Mot de passe, encore une fois : ").strip() != mdp:
        print("Les deux mots de passe sont differents. Rien n'a ete fait.")
        return 1
    existant = next((compte for compte in utilisateurs.lister() if compte["nom"].lower() == nom.lower()), None)
    try:
        if existant:
            utilisateurs.reinitialiser_mot_de_passe(existant["id"], mdp)
            print(f"Mot de passe de {existant['nom']} change.")
        else:
            utilisateurs.creer(nom, mdp)
            print(f"Compte {nom} cree.")
    except ErreurUtilisateur as erreur:
        print("Erreur :", erreur)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
