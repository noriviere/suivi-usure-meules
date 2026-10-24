import os
import re
import threading
import time
import unicodedata

from .. import config
from .valider import CONFIG

FEUILLE, TABLEAU = "Data", "TableauData"
VERROU = threading.Lock()              # une seule écriture à la fois


def norm(texte):
    return " ".join(str(texte).split()).lower() if texte is not None else ""


FORCER_TEXTE = {norm(champ["nom"]) for champ in CONFIG["champs"] if champ.get("forcer_texte")}


class FichierOccupe(Exception):
    pass


# Chronométrage de la dernière écriture (secondes par étape), lu par la route puis écrit
# dans journal_chrono.csv. Modifié seulement sous VERROU : une écriture à la fois.
MESURES = {}
_PROGRESSION = None            # fonction appelée au début de chaque étape (pour la barre de chargement)


class _Etape:
    """with _Etape("sauvegarde"): ... ajoute la durée du bloc à MESURES["sauvegarde"]."""
    def __init__(self, nom):
        self.nom = nom

    def __enter__(self):
        if _PROGRESSION:
            try:
                _PROGRESSION(self.nom)
            except Exception:
                pass                  # l'affichage de l'avancement ne doit jamais bloquer l'écriture
        self.t0 = time.perf_counter()

    def __exit__(self, *_):
        MESURES[self.nom] = MESURES.get(self.nom, 0.0) + time.perf_counter() - self.t0


def _ecrire(cellule, nom, valeur):
    if isinstance(valeur, str):
        if norm(nom) in FORCER_TEXTE:
            cellule.NumberFormat = "@"
        elif re.fullmatch(r"[1-9]\d*(\.\d+)?|0(\.\d+)?", valeur):
            valeur = float(valeur) if "." in valeur else int(valeur)
        else:
            cellule.NumberFormat = "@"
    cellule.Value = valeur


def _copier_formules(tbl, source, cible):
    """Recopie dans la ligne `cible` les formules que la ligne `source` a
    et que `cible` n'a pas reçues d'Excel (références relatives ajustées)."""
    corps = tbl.DataBodyRange
    for indice_colonne in range(1, tbl.ListColumns.Count + 1):
        src, dst = corps.Cells(source, indice_colonne), corps.Cells(cible, indice_colonne)
        if src.HasFormula and not dst.HasFormula:
            dst.FormulaR1C1 = src.FormulaR1C1


def _copier_formats(tbl, source, cible):
    """Une nouvelle ligne reçoit le format « par défaut » des colonnes du tableau,
    qui peut différer de celui des lignes existantes (fonds gris, polices...).
    On recopie donc le format de la ligne précédente, cellule par cellule.
    On n'utilise ni le presse-papiers ni « Coller le format », pour ne pas
    fragmenter les règles de mise en forme conditionnelle."""
    corps = tbl.DataBodyRange
    for indice_colonne in range(1, tbl.ListColumns.Count + 1):
        src, dst = corps.Cells(source, indice_colonne), corps.Cells(cible, indice_colonne)
        try:
            dst.NumberFormat = src.NumberFormat
            dst.HorizontalAlignment = src.HorizontalAlignment
            dst.VerticalAlignment = src.VerticalAlignment
            dst.WrapText = src.WrapText
            # fond
            if src.Interior.Pattern == -4142:              # xlNone : pas de fond
                dst.Interior.Pattern = -4142
            else:
                dst.Interior.Pattern = src.Interior.Pattern
                dst.Interior.Color = src.Interior.Color
            # police
            dst.Font.Name = src.Font.Name
            dst.Font.Size = src.Font.Size
            dst.Font.Bold = src.Font.Bold
            dst.Font.Italic = src.Font.Italic
            dst.Font.Color = src.Font.Color
            # bordures (gauche, haut, bas, droite)
            for bord in (7, 8, 9, 10):
                bs, bd = src.Borders(bord), dst.Borders(bord)
                bd.LineStyle = bs.LineStyle
                if bs.LineStyle != -4142:
                    bd.Weight = bs.Weight
                    bd.Color = bs.Color
        except Exception:
            pass          # la mise en forme est cosmétique : elle ne doit jamais bloquer une saisie


def _sans_accent(texte):
    texte = unicodedata.normalize("NFD", str(texte))
    return "".join(caractere for caractere in texte if unicodedata.category(caractere) != "Mn").lower().strip()


def _onglet_defaut(wb, nom):
    """Trouve l'onglet sans tenir compte des accents ni des majuscules
    (« Data défaut » = « data defaut »)."""
    for ws in wb.Worksheets:
        if _sans_accent(ws.Name) == _sans_accent(nom):
            return ws
    raise ValueError(f"Onglet « {nom} » introuvable dans le classeur.")


def _ajouter_dans_tableau(excel, tbl, valeurs, alias=None, tolerant=False):
    """Ajoute une ligne dans le tableau `tbl`.
    alias : {nom du champ: [autres noms possibles de la colonne]}.
    tolerant : les champs sans colonne sont ignorés (et renvoyés) au lieu de bloquer.
    Renvoie (numéro de ligne Excel, colonnes calculées, champs ignorés)."""
    alias = alias or {}
    colonnes = {norm(colonne.Name): colonne.Index for colonne in tbl.ListColumns}
    cibles, ignores = {}, []
    for nom in valeurs:
        for candidat in [nom] + alias.get(nom, []):
            if norm(candidat) in colonnes:
                cibles[nom] = colonnes[norm(candidat)]
                break
        else:
            ignores.append(nom)
    if ignores and not tolerant:
        raise ValueError(
            f"Colonnes introuvables dans {tbl.Name} : {ignores}. "
            f"Ajoutez-les dans la ligne d'en-tête du tableau (même nom) "
            f"ou corrigez champs.json.")

    precedente = tbl.ListRows.Count
    with _Etape("ajout_ligne"):
        tbl.ListRows.Add()
    cible = precedente + 1
    if precedente > 0:
        with _Etape("formules"):
            _copier_formules(tbl, precedente, cible)
        with _Etape("formats"):
            _copier_formats(tbl, precedente, cible)

    corps = tbl.DataBodyRange
    with _Etape("valeurs"):
        for nom, valeur in valeurs.items():
            if valeur is not None and nom in cibles:
                _ecrire(corps.Cells(cible, cibles[nom]), nom, valeur)
    with _Etape("calcul"):
        excel.Calculate()

    utilises = set(cibles.values())
    calcules = {}
    for colonne in tbl.ListColumns:
        if colonne.Index not in utilises:
            calcules[colonne.Name.replace("\n", " ")] = corps.Cells(cible, colonne.Index).Text
    erreurs = [nom for nom, valeur in calcules.items() if str(valeur).startswith("#")]
    if erreurs:
        raise ValueError(f"Excel a renvoyé une erreur dans {tbl.Name} : {erreurs}")
    return corps.Cells(cible, 1).Row, calcules, ignores


def _ouvrir(excel, chemin, tentatives=6, pause=1.5):
    """Ouvre le classeur en écriture. S'il est occupé (ouvert par quelqu'un
    d'autre, donc en lecture seule), on réessaie quelques secondes."""
    for essai in range(tentatives):
        wb = None
        try:
            wb = excel.Workbooks.Open(chemin, ReadOnly=False, Notify=False)
            if not wb.ReadOnly:
                return wb
            wb.Close(SaveChanges=False)
        except Exception:
            if wb is not None:
                try:
                    wb.Close(SaveChanges=False)
                except Exception:
                    pass
        if essai < tentatives - 1:
            time.sleep(pause)
    raise FichierOccupe("Le fichier est utilisé par quelqu'un d'autre : "
                        "rien n'a été enregistré. Réessayez dans un instant.")


def ajouter_ligne(valeurs, chemin=None, defaut=False, progression=None, mesures=None):
    """valeurs : dict nom de colonne -> valeur déjà validée.
    defaut : True = ajouter aussi la ligne dans l'onglet des meules défectueuses.
    progression : fonction(nom_etape) appelée à chaque étape ; mesures : dict rempli avec les durées.
    Renvoie (numéro de ligne Excel, colonnes calculées, infos sur l'onglet défaut)."""
    if config.MODE_DEMO:                       # démonstration : classeur de fausses données, sans Excel
        from . import ecriture_demo
        return ecriture_demo.ajouter_ligne(valeurs, defaut=defaut, progression=progression, mesures=mesures)
    chemin = os.path.abspath(chemin or config.FICHIER)
    import pythoncom
    import win32com.client as win32
    cfg = CONFIG.get("defaut") or {}
    global _PROGRESSION
    if progression:
        progression("attente")                 # si une autre écriture est en cours, on patiente ici
    with VERROU:
        _PROGRESSION = progression
        MESURES.clear()
        sauvegarde.sauvegarder(chemin)            # copie de sécurité AVANT toute écriture (n'arrête jamais la saisie si elle échoue)
        t_debut = time.perf_counter()
        pythoncom.CoInitialize()
        excel = wb = None
        try:
            with _Etape("lancement_excel"):
                excel = win32.DispatchEx("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
            with _Etape("ouverture"):
                wb = _ouvrir(excel, chemin)

            info_defaut = None
            if defaut:
                # on vérifie l'onglet AVANT d'écrire quoi que ce soit
                ws_d = _onglet_defaut(wb, cfg["onglet"])
                if ws_d.ListObjects.Count == 0:
                    raise ValueError(f"L'onglet « {ws_d.Name} » ne contient pas de tableau Excel.")
                tbl_d = ws_d.ListObjects(1)

            tbl = wb.Worksheets(FEUILLE).ListObjects(TABLEAU)
            ligne = None
            calcules = {}
            if not defaut or cfg.get("garder_dans_data", True):
                ligne, calcules, _ = _ajouter_dans_tableau(excel, tbl, valeurs)
            if defaut:
                l2, _, ignores = _ajouter_dans_tableau(
                    excel, tbl_d, valeurs, cfg.get("alias_colonnes"), tolerant=True)
                info_defaut = {"onglet": ws_d.Name, "ligne": l2, "colonnes_absentes": ignores}
                ligne = ligne or l2

            with _Etape("sauvegarde"):
                wb.Save()                              # seul moment où le fichier est modifié
            return ligne, calcules, info_defaut
        finally:
            with _Etape("fermeture"):
                if wb is not None:
                    wb.Close(SaveChanges=False)        # sans effet si déjà enregistré
                if excel is not None:
                    excel.Quit()
                pythoncom.CoUninitialize()
            MESURES["total_excel"] = time.perf_counter() - t_debut
            _PROGRESSION = None
            if mesures is not None:
                mesures.update(MESURES)
