"""Adapter Excel (COM) du module d'écriture, utilisé en production : Excel garde les formules, les formats
et la mise en forme conditionnelle du classeur. Le déroulé (verrou, copie de sécurité, onglet Data défaut,
contrôle des colonnes) est dans ecriture.py ; ici, seulement ce qui parle à Excel."""
import time

from .ecriture import FEUILLE, TABLEAU, FichierOccupe

SANS_FOND = -4142              # xlNone : pas de fond, pas de bordure


def _copier_formules(tableau, source, cible):
    """Recopie dans la ligne `cible` les formules que la ligne `source` a
    et que `cible` n'a pas reçues d'Excel (références relatives ajustées)."""
    corps = tableau.DataBodyRange
    for indice_colonne in range(1, tableau.ListColumns.Count + 1):
        depart, arrivee = corps.Cells(source, indice_colonne), corps.Cells(cible, indice_colonne)
        if depart.HasFormula and not arrivee.HasFormula:
            arrivee.FormulaR1C1 = depart.FormulaR1C1


def _copier_formats(tableau, source, cible):
    """Une nouvelle ligne reçoit le format « par défaut » des colonnes du tableau,
    qui peut différer de celui des lignes existantes (fonds gris, polices...).
    On recopie donc le format de la ligne précédente, cellule par cellule.
    On n'utilise ni le presse-papiers ni « Coller le format », pour ne pas
    fragmenter les règles de mise en forme conditionnelle."""
    corps = tableau.DataBodyRange
    for indice_colonne in range(1, tableau.ListColumns.Count + 1):
        depart, arrivee = corps.Cells(source, indice_colonne), corps.Cells(cible, indice_colonne)
        try:
            arrivee.NumberFormat = depart.NumberFormat
            arrivee.HorizontalAlignment = depart.HorizontalAlignment
            arrivee.VerticalAlignment = depart.VerticalAlignment
            arrivee.WrapText = depart.WrapText
            # fond
            if depart.Interior.Pattern == SANS_FOND:
                arrivee.Interior.Pattern = SANS_FOND
            else:
                arrivee.Interior.Pattern = depart.Interior.Pattern
                arrivee.Interior.Color = depart.Interior.Color
            # police
            arrivee.Font.Name = depart.Font.Name
            arrivee.Font.Size = depart.Font.Size
            arrivee.Font.Bold = depart.Font.Bold
            arrivee.Font.Italic = depart.Font.Italic
            arrivee.Font.Color = depart.Font.Color
            # bordures (gauche, haut, bas, droite)
            for bord in (7, 8, 9, 10):
                bord_depart, bord_arrivee = depart.Borders(bord), arrivee.Borders(bord)
                bord_arrivee.LineStyle = bord_depart.LineStyle
                if bord_depart.LineStyle != SANS_FOND:
                    bord_arrivee.Weight = bord_depart.Weight
                    bord_arrivee.Color = bord_depart.Color
        except Exception:
            pass          # la mise en forme est cosmétique : elle ne doit jamais bloquer une saisie


def _ecrire(cellule, valeur):
    if isinstance(valeur, str):
        cellule.NumberFormat = "@"           # ecriture.py a déjà converti les nombres : un texte reste un texte
    cellule.Value = valeur


def _ouvrir(excel, chemin, tentatives=6, pause=1.5):
    """Ouvre le classeur en écriture. S'il est occupé (ouvert par quelqu'un
    d'autre, donc en lecture seule), on réessaie quelques secondes."""
    for essai in range(tentatives):
        classeur = None
        try:
            classeur = excel.Workbooks.Open(chemin, ReadOnly=False, Notify=False)
            if not classeur.ReadOnly:
                return classeur
            classeur.Close(SaveChanges=False)
        except Exception:
            if classeur is not None:
                try:
                    classeur.Close(SaveChanges=False)
                except Exception:
                    pass
        if essai < tentatives - 1:
            time.sleep(pause)
    raise FichierOccupe("Le classeur est utilisé par quelqu'un d'autre : "
                        "rien n'a été enregistré. Réessayez dans un instant.")


class ClasseurExcel:
    def ouvrir(self, chemin, etape):
        import pythoncom
        import win32com.client as win32
        pythoncom.CoInitialize()
        excel = None
        try:
            with etape("lancement_excel"):
                excel = win32.DispatchEx("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
            with etape("ouverture"):
                return ClasseurExcelOuvert(excel, _ouvrir(excel, chemin))
        except BaseException:
            if excel is not None:
                excel.Quit()
            pythoncom.CoUninitialize()
            raise


class ClasseurExcelOuvert:
    def __init__(self, excel, classeur):
        self.excel, self.classeur = excel, classeur

    def onglets(self):
        return [feuille.Name for feuille in self.classeur.Worksheets]

    def tableau_data(self):
        try:
            return self.classeur.Worksheets(FEUILLE).ListObjects(TABLEAU)
        except Exception:                      # COM lève une erreur générique si l'onglet ou le tableau manque
            return None

    def tableau_de(self, onglet):
        feuille = self.classeur.Worksheets(onglet)
        return feuille.ListObjects(1) if feuille.ListObjects.Count else None

    def colonnes(self, tableau):
        return [colonne.Name for colonne in tableau.ListColumns]

    def ajouter(self, tableau, cibles, etape):
        """Ajoute une ligne au tableau et renvoie (numéro de ligne Excel, {colonne calculée: texte affiché})."""
        index = {colonne.Name: colonne.Index for colonne in tableau.ListColumns}
        precedente = tableau.ListRows.Count
        with etape("ajout_ligne"):
            tableau.ListRows.Add()
        cible = precedente + 1
        with etape("formules"):                # étape annoncée même sur un tableau vide : rien à recopier
            if precedente > 0:
                _copier_formules(tableau, precedente, cible)
        with etape("formats"):
            if precedente > 0:
                _copier_formats(tableau, precedente, cible)
        corps = tableau.DataBodyRange
        with etape("valeurs"):
            for colonne, valeur in cibles.items():
                if valeur is not None:
                    _ecrire(corps.Cells(cible, index[colonne]), valeur)
        with etape("calcul"):
            self.excel.Calculate()
        calcules = {colonne.Name.replace("\n", " "): corps.Cells(cible, colonne.Index).Text
                    for colonne in tableau.ListColumns if colonne.Name not in cibles}
        return corps.Cells(cible, 1).Row, calcules

    def enregistrer(self):
        self.classeur.Save()

    def fermer(self):
        import pythoncom
        try:
            self.classeur.Close(SaveChanges=False)        # sans effet si déjà enregistré
        finally:
            self.excel.Quit()
            pythoncom.CoUninitialize()
