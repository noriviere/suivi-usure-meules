"""Adapter Excel (COM) du module d'écriture, utilisé en production : Excel garde les formules, les formats
et la mise en forme conditionnelle du classeur. Le déroulé (verrou, copie de sécurité, onglet Data défaut,
contrôle des colonnes) est dans ecriture.py ; ici, seulement ce qui parle à Excel."""
import time

from .ecriture import FEUILLE, TABLEAU, FichierOccupe, sans_accent


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


def _ecrire(cellule, valeur):
    if isinstance(valeur, str):
        cellule.NumberFormat = "@"           # ecriture.py a déjà converti les nombres : un texte reste un texte
    cellule.Value = valeur


def _onglet_defaut(wb, nom):
    """Trouve l'onglet sans tenir compte des accents ni des majuscules
    (« Data défaut » = « data defaut »). Utilisé aussi par outils/nettoyage.py."""
    for ws in wb.Worksheets:
        if sans_accent(ws.Name) == sans_accent(nom):
            return ws
    raise ValueError(f"Onglet « {nom} » introuvable dans le classeur.")


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
                return _ClasseurOuvert(excel, _ouvrir(excel, chemin))
        except BaseException:
            if excel is not None:
                excel.Quit()
            pythoncom.CoUninitialize()
            raise


class _ClasseurOuvert:
    def __init__(self, excel, wb):
        self.excel, self.wb = excel, wb

    def onglets(self):
        return [ws.Name for ws in self.wb.Worksheets]

    def tableau_data(self):
        return self.wb.Worksheets(FEUILLE).ListObjects(TABLEAU)

    def tableau_de(self, onglet):
        ws = self.wb.Worksheets(onglet)
        return ws.ListObjects(1) if ws.ListObjects.Count else None

    def colonnes(self, tbl):
        return [colonne.Name for colonne in tbl.ListColumns]

    def ajouter(self, tbl, cibles, etape):
        """Ajoute une ligne au tableau et renvoie (numéro de ligne Excel, {colonne calculée: texte affiché})."""
        index = {colonne.Name: colonne.Index for colonne in tbl.ListColumns}
        precedente = tbl.ListRows.Count
        with etape("ajout_ligne"):
            tbl.ListRows.Add()
        cible = precedente + 1
        if precedente > 0:
            with etape("formules"):
                _copier_formules(tbl, precedente, cible)
            with etape("formats"):
                _copier_formats(tbl, precedente, cible)
        corps = tbl.DataBodyRange
        with etape("valeurs"):
            for colonne, valeur in cibles.items():
                if valeur is not None:
                    _ecrire(corps.Cells(cible, index[colonne]), valeur)
        with etape("calcul"):
            self.excel.Calculate()
        calcules = {colonne.Name.replace("\n", " "): corps.Cells(cible, colonne.Index).Text
                    for colonne in tbl.ListColumns if colonne.Name not in cibles}
        return corps.Cells(cible, 1).Row, calcules

    def enregistrer(self):
        self.wb.Save()

    def fermer(self):
        import pythoncom
        try:
            self.wb.Close(SaveChanges=False)        # sans effet si déjà enregistré
        finally:
            self.excel.Quit()
            pythoncom.CoUninitialize()
