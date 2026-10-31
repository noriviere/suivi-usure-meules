"""Écriture d'une saisie dans le classeur : tout le déroulé (verrou, copie de sécurité, onglet Data défaut,
contrôle des colonnes, étapes de la barre de chargement, chronométrage) est ici, une seule fois.
Le classeur lui-même est manipulé par un adapter :
  - classeur_excel.ClasseurExcel : Excel par COM, en production ;
  - classeur_openpyxl.ClasseurOpenpyxl : sans Excel, en mode démo et dans les tests."""
import contextlib
import os
import re
import threading
import time
import unicodedata

from .. import config
from . import sauvegarde
from .reglages import BASE as CONFIG      # champs.json d'origine

FEUILLE, TABLEAU = "Data", "TableauData"
VERROU = threading.Lock()              # une seule écriture à la fois
PAUSE_DEMO_S = 0.35                    # en démo, petite pause par étape pour que la barre de chargement soit visible


def norm(texte):
    return " ".join(str(texte).split()).lower() if texte is not None else ""


def sans_accent(texte):
    texte = unicodedata.normalize("NFD", str(texte))
    return "".join(caractere for caractere in texte if unicodedata.category(caractere) != "Mn").lower().strip()


FORCER_TEXTE = {norm(champ["nom"]) for champ in CONFIG["champs"] if champ.get("forcer_texte")}


class FichierOccupe(Exception):
    pass


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
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.mesures[nom] = self.mesures.get(nom, 0.0) + time.perf_counter() - t0


def _preparer(valeurs):
    """Un texte qui ressemble à un nombre devient un nombre, sauf pour les champs à garder en texte
    (matricules, n° article...). Tout ce qui reste texte est écrit comme texte dans le classeur."""
    prepares = {}
    for nom, valeur in valeurs.items():
        if isinstance(valeur, str) and norm(nom) not in FORCER_TEXTE and re.fullmatch(r"[1-9]\d*(\.\d+)?|0(\.\d+)?", valeur):
            valeur = float(valeur) if "." in valeur else int(valeur)
        prepares[nom] = valeur
    return prepares


def _cibles(colonnes, valeurs, tableau, alias=None, tolerant=False):
    """Associe chaque champ à une colonne du tableau (nom exact, sinon un de ses alias).
    Renvoie ({nom de colonne: valeur ou None}, champs sans colonne). Sans `tolerant`, un champ sans colonne bloque tout."""
    alias = alias or {}
    par_nom = {norm(colonne): colonne for colonne in colonnes if colonne is not None}
    cibles, ignores = {}, []
    for nom, valeur in valeurs.items():
        colonne = next((par_nom[norm(c)] for c in [nom] + alias.get(nom, []) if norm(c) in par_nom), None)
        if colonne is None:
            ignores.append(nom)
        else:
            cibles[colonne] = valeur          # une valeur vide n'est pas écrite, mais la colonne reste « saisie »
    if ignores and not tolerant:
        raise ValueError(
            f"Colonnes introuvables dans {tableau} : {ignores}. "
            f"Ajoutez-les dans la ligne d'en-tête du tableau (même nom) "
            f"ou corrigez champs.json.")
    return cibles, ignores


def _onglet(onglets, nom):
    """Trouve l'onglet sans tenir compte des accents ni des majuscules (« Data défaut » = « data defaut »)."""
    for onglet in onglets:
        if sans_accent(onglet) == sans_accent(nom):
            return onglet
    raise ValueError(f"Onglet « {nom} » introuvable dans le classeur.")


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
    cfg = CONFIG.get("defaut") or {}
    valeurs = _preparer(valeurs)
    suivi = _Suivi(progression)
    suivi.annoncer("attente")                 # si une autre écriture est en cours, on patiente ici
    with VERROU:
        sauvegarde.sauvegarder(chemin)        # copie de sécurité AVANT toute écriture (n'arrête jamais la saisie si elle échoue)
        t_debut = time.perf_counter()
        ouvert = None
        try:
            ouvert = classeur.ouvrir(chemin, suivi.etape)

            ecritures = []                    # (tableau, nom affiché, {colonne: valeur}, champs ignorés)
            if not defaut or cfg.get("garder_dans_data", True):
                tbl = ouvert.tableau_data()
                ecritures.append((tbl, TABLEAU, *_cibles(ouvert.colonnes(tbl), valeurs, TABLEAU)))
            if defaut:
                onglet = _onglet(ouvert.onglets(), cfg["onglet"])
                tbl_d = ouvert.tableau_de(onglet)
                if tbl_d is None:
                    raise ValueError(f"L'onglet « {onglet} » ne contient pas de tableau Excel.")
                ecritures.append((tbl_d, onglet, *_cibles(ouvert.colonnes(tbl_d), valeurs, onglet,
                                                          cfg.get("alias_colonnes"), tolerant=True)))

            resultats = []
            for tbl, nom, cibles, ignores in ecritures:
                numero, calcules = ouvert.ajouter(tbl, cibles, suivi.etape)
                erreurs = [colonne for colonne, valeur in calcules.items() if str(valeur).startswith("#")]
                if erreurs:
                    raise ValueError(f"Excel a renvoyé une erreur dans {nom} : {erreurs}")
                resultats.append((numero, calcules, ignores))

            with suivi.etape("sauvegarde"):
                ouvert.enregistrer()          # seul moment où le fichier est modifié

            ligne, calcules, info_defaut = None, {}, None
            if not defaut or cfg.get("garder_dans_data", True):
                ligne, calcules, _ = resultats[0]
            if defaut:
                l2, _, ignores = resultats[-1]
                info_defaut = {"onglet": ecritures[-1][1], "ligne": l2, "colonnes_absentes": ignores}
                ligne = ligne or l2
            return ligne, calcules, info_defaut
        finally:
            with suivi.etape("fermeture"):
                if ouvert is not None:
                    ouvert.fermer()
            suivi.mesures["total_excel"] = time.perf_counter() - t_debut
            if mesures is not None:
                mesures.update(suivi.mesures)
