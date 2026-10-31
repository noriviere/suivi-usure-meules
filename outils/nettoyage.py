"""Nettoyage du fichier Excel (à lancer à la main, serveur arrêté, fichier fermé dans Excel).

  python -m outils.nettoyage              -> APERÇU seulement : ne modifie rien, écrit nettoyage_apercu.csv
  python -m outils.nettoyage --appliquer  -> fait une copie de sécurité PUIS :
        1. complète les matricules à 4 chiffres (534 -> 0534, en texte)
        2. supprime les lignes dont « Nb faces/meule de 89 mm » est très éloigné des autres
           meules identiques (même règle que l'onglet Contrôle qualité : zone de Tukey x3)
     Les lignes supprimées sont sauvegardées dans lignes_supprimees_AAAAMMJJ_HHMM.csv.
"""
import csv
import datetime
import os
import shutil
import sys

from backend import config
from backend.services.controle import anomalies
from backend.services.donnees import tableau, norm
from backend.services.reglages import BASE as CONFIG

MOTIF = "très éloigné"


def plan():
    donnees_tableau = tableau()
    cles = donnees_tableau["cles"]
    i_mat = [position for position, cle in enumerate(cles) if cle.startswith("matricule")]
    a_corriger = 0
    for ligne in donnees_tableau["lignes"]:
        for position in i_mat:
            valeur = ligne[position + 1]
            if isinstance(valeur, float) and valeur.is_integer():
                valeur = int(valeur)
            if valeur not in (None, "") and str(valeur).strip().isdigit() and len(str(valeur).strip()) < 4:
                a_corriger += 1
    lignes_a_supprimer = sorted({anomalie["ligne"] for anomalie in anomalies()["anomalies"] if anomalie["motif"].startswith(MOTIF)})
    par_ligne = {ligne[0]: ligne for ligne in donnees_tableau["lignes"]}
    return donnees_tableau, a_corriger, [par_ligne[numero_ligne] for numero_ligne in lignes_a_supprimer if numero_ligne in par_ligne]


def ecrire_csv(chemin, donnees_tableau, lignes):
    with open(chemin, "w", newline="", encoding="utf-8-sig") as fichier:
        ecrivain = csv.writer(fichier, delimiter=";")
        ecrivain.writerow(["Ligne Excel"] + donnees_tableau["entetes"])
        ecrivain.writerows(lignes)


def main():
    appliquer = "--appliquer" in sys.argv
    print("Fichier :", config.FICHIER)
    donnees_tableau, nb_mat, a_suppr = plan()
    idx = {cle: position + 1 for position, cle in enumerate(donnees_tableau["cles"])}
    print(f"Matricules à compléter à 4 chiffres : {nb_mat} cellule(s)")
    print(f"Lignes à supprimer (valeurs très éloignées) : {len(a_suppr)}")
    for ligne in a_suppr[:80]:
        print(f"  ligne {ligne[0]:>5}  meule {ligne[idx['n° article meule']]}  matière {ligne[idx['matière']]}  "
              f"machine {ligne[idx['n° de machine']]}  date {ligne[idx['date montage']]}  "
              f"faces/meule {ligne[idx['nb faces/meule de 89 mm']]}")
    if len(a_suppr) > 80:
        print("  ... (liste complète dans nettoyage_apercu.csv)")
    ecrire_csv(os.path.join(config.DOSSIER_DONNEES, "nettoyage_apercu.csv"), donnees_tableau, a_suppr)
    if not appliquer:
        print("\nAPERÇU : rien n'a été modifié. Pour appliquer : python -m outils.nettoyage --appliquer")
        return
    if input("\nTapez OUI pour modifier le fichier (une copie de sécurité sera faite) : ").strip() != "OUI":
        print("Annulé.")
        return

    horodatage = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    base, ext = os.path.splitext(os.path.abspath(config.FICHIER))
    copie = f"{base}_AVANT_NETTOYAGE_{horodatage}{ext}"
    shutil.copy2(config.FICHIER, copie)
    print("Copie de sécurité :", copie)
    csv_supp = os.path.join(config.DOSSIER_DONNEES, f"lignes_supprimees_{horodatage}.csv")
    ecrire_csv(csv_supp, donnees_tableau, a_suppr)

    import pythoncom
    import win32com.client as win32
    from backend.services.ecriture import FEUILLE, TABLEAU, FichierOccupe, trouver_onglet

    pythoncom.CoInitialize()
    excel = wb = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(os.path.abspath(config.FICHIER), ReadOnly=False, Notify=False)
        if wb.ReadOnly:
            raise FichierOccupe("Le fichier est ouvert ailleurs : fermez-le (et arrêtez le serveur) puis relancez.")

        def corriger_matricules(tbl):
            nb_corriges = 0
            for col in tbl.ListColumns:
                if not norm(col.Name).startswith("matricule") or tbl.ListRows.Count == 0:
                    continue
                rng = col.DataBodyRange
                brut = rng.Value2
                valeurs = [brut] if tbl.ListRows.Count == 1 else [ligne_brute[0] for ligne_brute in brut]
                nouvelles = []
                for valeur in valeurs:
                    if isinstance(valeur, float) and valeur.is_integer():
                        valeur = int(valeur)
                    if valeur not in (None, "") and str(valeur).strip().isdigit() and len(str(valeur).strip()) < 4:
                        valeur = str(valeur).strip().zfill(4)
                        nb_corriges += 1
                    elif isinstance(valeur, (int, float)):
                        valeur = str(int(valeur)) if float(valeur).is_integer() else valeur
                    nouvelles.append(valeur)
                if nouvelles != valeurs:
                    rng.NumberFormat = "@"
                    rng.Value2 = tuple((valeur,) for valeur in nouvelles)
            return nb_corriges

        tbl = wb.Worksheets(FEUILLE).ListObjects(TABLEAU)
        n_data = corriger_matricules(tbl)
        n_def = 0
        try:
            ws_d = wb.Worksheets(trouver_onglet([ws.Name for ws in wb.Worksheets], CONFIG["defaut"]["onglet"]))
            if ws_d.ListObjects.Count:
                n_def = corriger_matricules(ws_d.ListObjects(1))
        except Exception as erreur:
            print("Onglet défaut non traité :", erreur)
        print(f"Matricules corrigés : {n_data} (Data) + {n_def} (onglet défaut)")

        # suppression : de bas en haut, en vérifiant à chaque fois que la ligne est bien la bonne
        premiere = tbl.HeaderRowRange.Row + 1
        col_art = [colonne.Index for colonne in tbl.ListColumns if norm(colonne.Name) == "n° article meule"][0]
        for ligne in sorted(a_suppr, reverse=True):
            rang_dans_tableau = ligne[0] - premiere + 1
            lu = tbl.ListRows(rang_dans_tableau).Range.Cells(1, col_art).Value
            if str(lu).strip() != str(ligne[idx["n° article meule"]]).strip():
                raise ValueError(f"La ligne {ligne[0]} ne correspond plus (lu {lu!r}) : le fichier a changé depuis l'aperçu. Rien n'est enregistré.")
        for ligne in sorted(a_suppr, reverse=True):
            tbl.ListRows(ligne[0] - premiere + 1).Delete()
        print(f"Lignes supprimées : {len(a_suppr)} (sauvegardées dans {csv_supp})")
        wb.Save()
        print("Fichier enregistré.")
    finally:
        if wb is not None:
            wb.Close(SaveChanges=False)
        if excel is not None:
            excel.Quit()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
