"""Écriture d'une saisie dans le classeur : tout le déroulé (verrou, copie de sécurité, onglet Data défaut,
contrôle des colonnes, étapes de la barre de chargement, chronométrage) est ici, une seule fois.
Le classeur lui-même est manipulé par un adapter :
  - classeur_excel.ClasseurExcel : Excel par COM, en production ;
  - classeur_openpyxl.ClasseurOpenpyxl : sans Excel, en mode démo et dans les tests.
Les noms d'étapes (« lancement_excel »...) sont ceux qu'attendent la barre de chargement et le journal de
chronométrage : ils restent identiques quel que soit l'adapter."""
import contextlib
import dataclasses
import os
import re
import threading
import time
import unicodedata

from .. import config
from . import sauvegarde
from .donnees import norm
from .reglages import BASE as CONFIG      # champs.json d'origine

FEUILLE, TABLEAU = "Data", "TableauData"
VERROU = threading.Lock()              # une seule écriture à la fois
PAUSE_DEMO_S = 0.35                    # en démo, petite pause par étape pour que la barre de chargement soit visible
FORCER_TEXTE = {norm(champ["nom"]) for champ in CONFIG["champs"] if champ.get("forcer_texte")}


class FichierOccupe(Exception):
    pass


def sans_accent(texte):
    texte = unicodedata.normalize("NFD", str(texte))
    return "".join(caractere for caractere in texte if unicodedata.category(caractere) != "Mn").lower().strip()


def trouver_onglet(onglets, nom):
    """Parmi les noms d'onglets du classeur, celui qui vaut `nom` sans tenir compte des accents ni des majuscules
    (« Data défaut » = « data defaut »). Utilisé aussi par outils/nettoyage.py."""
    for onglet in onglets:
        if sans_accent(onglet) == sans_accent(nom):
            return onglet
    raise ValueError(f"Onglet « {nom} » introuvable dans le classeur.")


class _Suivi:
    """Annonce les étapes à la barre de chargement et chronomètre chacune (secondes, cumulées)."""
    def __init__(self, progression):
        self.progression = progression
        self.mesures = {}

    def annoncer(self, nom):
        if self.progression:
            try:
                self.progression(nom)
            except Exception:
                pass                  # l'affichage de l'avancement ne doit jamais bloquer l'écriture

    @contextlib.contextmanager
    def etape(self, nom):
        self.annoncer(nom)
        debut = time.perf_counter()
        try:
            yield
        finally:
            self.mesures[nom] = self.mesures.get(nom, 0.0) + time.perf_counter() - debut


@dataclasses.dataclass
class _EcritureTableau:
    """Une ligne à ajouter dans un tableau du classeur, puis son résultat."""
    tableau: object
    nom: str                      # nom du tableau ou de l'onglet, pour les messages
    cibles: dict                  # {nom de colonne: valeur}
    ignores: list                 # champs sans colonne (seulement possible dans l'onglet Data défaut)
    numero: int = None
    calcules: dict = None


def _preparer(valeurs):
    """Un texte qui ressemble à un nombre devient un nombre, sauf pour les champs à garder en texte
    (matricules, n° article...). Tout ce qui reste texte est écrit comme texte dans le classeur."""
    prepares = {}
    for nom, valeur in valeurs.items():
        if isinstance(valeur, str) and norm(nom) not in FORCER_TEXTE and re.fullmatch(r"[1-9]\d*(\.\d+)?|0(\.\d+)?", valeur):
            valeur = float(valeur) if "." in valeur else int(valeur)
        prepares[nom] = valeur
    return prepares


def _cibles(colonnes, valeurs, nom_tableau, alias=None, tolerant=False):
    """Associe chaque champ à une colonne du tableau (nom exact, sinon un de ses alias).
    Renvoie ({nom de colonne: valeur ou None}, champs sans colonne). Sans `tolerant`, un champ sans colonne bloque tout."""
    alias = alias or {}
    par_nom = {norm(colonne): colonne for colonne in colonnes if colonne is not None}
    cibles, ignores = {}, []
    for champ, valeur in valeurs.items():
        noms_possibles = [norm(candidat) for candidat in [champ] + alias.get(champ, [])]
        colonne = next((par_nom[candidat] for candidat in noms_possibles if candidat in par_nom), None)
        if colonne is None:
            ignores.append(champ)
        else:
            cibles[colonne] = valeur          # une valeur vide n'est pas écrite, mais la colonne reste « saisie »
    if ignores and not tolerant:
        raise ValueError(
            f"Colonnes introuvables dans {nom_tableau} : {ignores}. "
            f"Ajoutez-les dans la ligne d'en-tête du tableau (même nom) "
            f"ou corrigez champs.json.")
    return cibles, ignores


_CLASSEUR = None


def _classeur_par_defaut():
    """L'adapter choisi une fois d'après la configuration : openpyxl en démo, Excel sinon."""
    global _CLASSEUR
    if _CLASSEUR is None:
        if config.MODE_DEMO:
            from .classeur_openpyxl import ClasseurOpenpyxl
            _CLASSEUR = ClasseurOpenpyxl(pause_s=PAUSE_DEMO_S)
        else:
            from .classeur_excel import ClasseurExcel
            _CLASSEUR = ClasseurExcel()
    return _CLASSEUR


def ajouter_ligne(valeurs, chemin=None, defaut=False, progression=None, mesures=None, classeur=None):
    """valeurs : dict nom de colonne -> valeur déjà validée.
    defaut : True = meule défectueuse, la ligne va aussi dans l'onglet Data défaut.
    progression : fonction(nom_etape) appelée à chaque étape ; mesures : dict rempli avec les durées.
    classeur : adapter à utiliser (par défaut, celui de la configuration).
    Renvoie (numéro de ligne Excel, colonnes calculées, infos sur l'onglet Data défaut).
    Jamais d'écriture partielle : tout est vérifié avant d'écrire, et le classeur n'est enregistré qu'à la fin."""
    classeur = classeur or _classeur_par_defaut()
    chemin = os.path.abspath(chemin or config.FICHIER)
    reglage_defectueuse = CONFIG.get("defaut") or {}
    dans_data = not defaut or reglage_defectueuse.get("garder_dans_data", True)
    valeurs = _preparer(valeurs)
    suivi = _Suivi(progression)
    suivi.annoncer("attente")                 # si une autre écriture est en cours, on patiente ici
    with VERROU:
        sauvegarde.sauvegarder(chemin)        # copie de sécurité AVANT toute écriture (n'arrête jamais la saisie si elle échoue)
        debut = time.perf_counter()
        ouvert = None
        try:
            ouvert = classeur.ouvrir(chemin, suivi.etape)

            data = defectueuse = None         # tout est vérifié ici, avant la première écriture
            if dans_data:
                tableau = ouvert.tableau_data()
                if tableau is None:
                    raise ValueError(f"Tableau « {TABLEAU} » introuvable dans l'onglet {FEUILLE}.")
                data = _EcritureTableau(tableau, TABLEAU, *_cibles(ouvert.colonnes(tableau), valeurs, TABLEAU))
            if defaut:
                onglet = trouver_onglet(ouvert.onglets(), reglage_defectueuse["onglet"])
                tableau = ouvert.tableau_de(onglet)
                if tableau is None:
                    raise ValueError(f"L'onglet « {onglet} » ne contient pas de tableau Excel.")
                defectueuse = _EcritureTableau(tableau, onglet, *_cibles(
                    ouvert.colonnes(tableau), valeurs, onglet, reglage_defectueuse.get("alias_colonnes"), tolerant=True))

            for ecriture_prevue in (data, defectueuse):
                if ecriture_prevue is None:
                    continue
                ecriture_prevue.numero, ecriture_prevue.calcules = ouvert.ajouter(
                    ecriture_prevue.tableau, ecriture_prevue.cibles, suivi.etape)
                en_erreur = [colonne for colonne, valeur in ecriture_prevue.calcules.items() if str(valeur).startswith("#")]
                if en_erreur:
                    raise ValueError(f"Une formule du classeur est en erreur dans {ecriture_prevue.nom} : {en_erreur}")

            with suivi.etape("sauvegarde"):
                ouvert.enregistrer()          # seul moment où le fichier est modifié

            principale = data or defectueuse
            info_defectueuse = None
            if defectueuse is not None:
                info_defectueuse = {"onglet": defectueuse.nom, "ligne": defectueuse.numero,
                                    "colonnes_absentes": defectueuse.ignores}
            return principale.numero, principale.calcules, info_defectueuse
        finally:
            with suivi.etape("fermeture"):
                if ouvert is not None:
                    ouvert.fermer()
            suivi.mesures["total_excel"] = time.perf_counter() - debut
            if mesures is not None:
                mesures.update(suivi.mesures)
