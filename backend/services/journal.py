import csv
import datetime
import json
import os

from .. import config


def ecrire_journal(poste, valeurs, ligne_excel=None, avertissements=()):
    nouveau = not os.path.exists(config.JOURNAL)
    with open(config.JOURNAL, "a", newline="", encoding="utf-8-sig") as fichier:
        ecrivain = csv.writer(fichier, delimiter=";")
        if nouveau:
            ecrivain.writerow(["date_heure", "poste", "ligne_excel", "avertissements", "valeurs"])
        ecrivain.writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            poste,
            ligne_excel,
            " | ".join(avertissements),
            json.dumps(valeurs, ensure_ascii=False, default=str),
        ])


COLONNES_CHRONO = ["verification", "lancement_excel", "ouverture", "ajout_ligne", "formules", "formats",
                   "valeurs", "calcul", "sauvegarde", "fermeture", "total_excel", "total_requete"]


def ecrire_chrono(mesures):
    """Une ligne par enregistrement, durees en secondes. Ne doit jamais bloquer une saisie."""
    try:
        nouveau = not os.path.exists(config.JOURNAL_CHRONO)
        with open(config.JOURNAL_CHRONO, "a", newline="", encoding="utf-8-sig") as fichier:
            ecrivain = csv.writer(fichier, delimiter=";")
            if nouveau:
                ecrivain.writerow(["date_heure"] + COLONNES_CHRONO)
            ecrivain.writerow([datetime.datetime.now().isoformat(timespec="seconds")]
                       + [("%.2f" % mesures[colonne]).replace(".", ",") if colonne in mesures else "" for colonne in COLONNES_CHRONO])
    except Exception:
        pass
