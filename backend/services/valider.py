import math
import datetime

from .reglages import config as cfg     # cfg() = règles en vigueur


def _nombre(brut):
    """Accepte 34, "34" ou "34,5". Refuse les booléens, NaN et l'infini."""
    if isinstance(brut, bool):
        raise ValueError
    nombre = float(str(brut).replace(",", "."))
    if not math.isfinite(nombre):
        raise ValueError
    return nombre


def valider(donnees: dict, listes: dict):
    """Renvoie (valeurs propres, erreurs bloquantes, avertissements).
    `listes` : valeurs autorisées par nom de champ, lues dans Excel."""
    propres, erreurs, avertissements = {}, [], []
    configuration = cfg()

    for champ in configuration["champs"]:
        nom, type_ = champ["nom"], champ["type"]
        if type_ == "affichage":               # champ d'information : rien à enregistrer
            continue
        unite = f" {champ['unite']}" if champ.get("unite") else ""
        brut = donnees.get(nom)

        if brut is None or str(brut).strip() == "":
            if champ.get("obligatoire") and "auto_depuis" not in champ:
                erreurs.append(f"{nom} : champ obligatoire")
            propres[nom] = None
            continue

        try:
            if type_ == "entier":
                nombre = _nombre(brut)
                if not nombre.is_integer():
                    raise ValueError
                valeur = int(nombre)
            elif type_ == "decimal":
                valeur = _nombre(brut)
            elif type_ == "date":
                valeur = datetime.datetime.strptime(str(brut)[:10], "%Y-%m-%d")
            else:
                valeur = str(brut).strip()
        except ValueError:
            erreurs.append(f"{nom} : valeur invalide")
            continue

        if "min" in champ and type_ in ("entier", "decimal") and valeur < champ["min"]:
            erreurs.append(f"{nom} : doit être supérieur ou égal à {champ['min']}{unite}")
        if "max" in champ and type_ in ("entier", "decimal") and valeur > champ["max"]:
            erreurs.append(f"{nom} : ne doit pas dépasser {champ['max']}{unite}")
        if "longueur" in champ and len(valeur) != champ["longueur"]:
            erreurs.append(f"{nom} : doit contenir exactement {champ['longueur']} caractères")
        if type_ == "date" and configuration["regles"]["date_futur"] and valeur.date() > datetime.date.today():
            avertissements.append(f"{nom} : la date est dans le futur")

        if type_ == "liste":
            autorisees = champ.get("valeurs") or listes.get(nom)
            if autorisees is not None and valeur not in autorisees and champ.get("hors_liste") != "ignorer":
                if champ.get("hors_liste") == "avertir_et_commentaire":
                    avertissements.append(f"{nom} : « {valeur} » n'est pas prévu pour ce format")
                    if not str(donnees.get("Commentaire") or "").strip():
                        erreurs.append(f"Commentaire obligatoire : expliquez pourquoi {nom} « {valeur} » n'est pas prévu pour ce format")
                else:
                    erreurs.append(f"{nom} : « {valeur} » n'est pas une valeur autorisée")

        propres[nom] = valeur

    # Règles entre plusieurs champs
    debut, fin = propres.get("Compteur début"), propres.get("Compteur fin")
    if debut is not None and fin is not None and fin < debut:
        erreurs.append("Compteur fin : doit être supérieur ou égal au compteur début")
    haut_i = propres.get("Hauteur meule initiale, mm")
    haut_f = propres.get("Hauteur meule finale, mm")
    if haut_i is not None and haut_f is not None and haut_f > haut_i:
        erreurs.append("Hauteur finale : ne peut pas dépasser la hauteur initiale")

    return propres, erreurs, avertissements


if __name__ == "__main__":
    # Test rapide : python valider.py
    essai = {"Matricule démonteur": "12", "Compteur début": "-5", "Compteur fin": "100",
             "Vitesse de rotation": 50}
    print(valider(essai, {}))
