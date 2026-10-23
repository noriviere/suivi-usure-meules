"""Contrôle qualité du fichier : repère les lignes qui semblent absurdes.
Ne modifie JAMAIS le fichier : produit seulement une liste à vérifier."""
import datetime
import statistics
from collections import defaultdict

from .donnees import tableau, norm
from .listes import charger
from .valider import cfg

GRAVE, VERIF, MINEUR = "probable erreur", "à vérifier", "mineur"
ORDRE = {GRAVE: 0, VERIF: 1, MINEUR: 2}


def _num(valeur):
    return float(valeur) if isinstance(valeur, (int, float)) and not isinstance(valeur, bool) else None


def anomalies():
    configuration = cfg()
    coefficient = (configuration.get("controle_qualite") or {}).get("coefficient_eloigne", 3)   # plus grand = moins de lignes signalées
    donnees_tableau = tableau()
    cles, lignes = donnees_tableau["cles"], donnees_tableau["lignes"]
    idx = {cle: position + 1 for position, cle in enumerate(cles)}          # +1 : la colonne 0 = n° de ligne
    ref = charger()
    meules = {meule["code"] for meule in ref["meules"]}
    couples = {(norm(ref_format["format"]), norm(ref_format["matiere"])) for ref_format in ref["formats"]}
    machines = {norm(option) for option in (next((champ.get("options", []) for champ in configuration["champs"] if champ["nom"] == "N° de Machine"), []))}
    machines |= {norm(machine) for ref_format in ref["formats"] for machine in ref_format["machines"]}
    out = []

    def ajoute(ligne, col, motif, gravite):
        valeur = ligne[idx[col]] if col in idx else None
        out.append({"ligne": ligne[0], "colonne": donnees_tableau["entetes"][cles.index(col)] if col in idx else col,
                    "valeur": "" if valeur is None else str(valeur), "motif": motif, "gravite": gravite})

    def val(ligne, col):
        return ligne[idx[col]] if col in idx else None

    # 1. limites et types des champs numériques définis dans champs.json
    for champ in configuration["champs"]:
        cle = norm(champ["nom"])
        if champ["type"] not in ("entier", "decimal") or cle not in idx:
            continue
        for ligne in lignes:
            valeur = val(ligne, cle)
            if valeur in (None, ""):
                ajoute(ligne, cle, "valeur manquante", MINEUR if cle == "pression d'arrosage" else VERIF); continue
            nombre = _num(valeur)
            if nombre is None:
                ajoute(ligne, cle, "texte au lieu d'un nombre", GRAVE); continue
            if champ.get("min") is not None and nombre < champ["min"]:
                ajoute(ligne, cle, f"inférieur à {champ['min']:g}", GRAVE)
            if champ.get("max") is not None and nombre > champ["max"]:
                ajoute(ligne, cle, f"supérieur à {champ['max']:g} {champ.get('unite', '')}".strip(), GRAVE)

    # 2. cohérences entre colonnes
    for ligne in lignes:
        debut, fin = _num(val(ligne, "compteur début")), _num(val(ligne, "compteur fin"))
        if fin is not None and fin == 0:
            ajoute(ligne, "compteur fin", "égal à 0 (division impossible dans Excel)", GRAVE)
        if debut is not None and fin is not None and fin < debut:
            ajoute(ligne, "compteur fin", f"inférieur au compteur début ({debut:g})", GRAVE)
        hi, hf = _num(val(ligne, "hauteur meule initiale, mm")), _num(val(ligne, "hauteur meule finale, mm"))
        if hi is not None and hf is not None and hf > hi:
            ajoute(ligne, "hauteur meule finale, mm", f"supérieure à la hauteur initiale ({hi:g})", GRAVE)

    # 3. dates
    auj = datetime.date.today().isoformat()
    for ligne in lignes:
        valeur = val(ligne, "date montage")
        if not (isinstance(valeur, str) and len(valeur) == 10 and valeur[4] == "-"):
            ajoute(ligne, "date montage", "date absente ou écrite en texte", GRAVE)
        elif valeur > auj:
            ajoute(ligne, "date montage", "date dans le futur", GRAVE)
        elif valeur < "2015-01-01":
            ajoute(ligne, "date montage", "date très ancienne", VERIF)

    # 4. valeurs hors listes
    for ligne in lignes:
        if val(ligne, "matière") not in ("I", "C"):
            ajoute(ligne, "matière", "ni I ni C", GRAVE)
        if val(ligne, "face") not in ("A", "B"):
            ajoute(ligne, "face", "ni A ni B", GRAVE)
        article = val(ligne, "n° article meule")
        if article is not None and str(article) not in meules:
            ajoute(ligne, "n° article meule", "absent de « Liste Meule »", VERIF)
        machine = val(ligne, "n° de machine")
        if machines and norm(machine) not in machines:
            ajoute(ligne, "n° de machine", "machine inconnue", VERIF)
        fm = (norm(val(ligne, "format")), norm(val(ligne, "matière")))
        if fm[0] and fm not in couples:
            ajoute(ligne, "format", "combinaison format + matière absente de « Formats & matière »", VERIF)
        for col in ("matricule monteur", "matricule démonteur"):
            mat = val(ligne, col)
            if mat not in (None, "") and not (str(mat).isdigit() and len(str(mat)) == 4):
                ajoute(ligne, col, "n'a pas 4 chiffres (ex. 534 au lieu de 0534)", MINEUR)

    # 5. erreurs affichées par Excel (#DIV/0!, #VALUE!...)
    for ligne in lignes:
        for col, position in idx.items():
            valeur = ligne[position]
            if isinstance(valeur, str) and valeur.startswith("#"):
                ajoute(ligne, col, f"Excel affiche {valeur}", GRAVE)

    # 6. durée de vie très éloignée des autres meules identiques (zone de Tukey, coefficient K)
    col = "nb faces/meule de 89 mm"
    if col in idx and configuration["regles"]["controle_eloigne"]:
        groupes = defaultdict(list)
        for ligne in lignes:
            nombre = _num(val(ligne, col))
            if nombre is not None:
                groupes[(val(ligne, "n° article meule"), val(ligne, "matière"))].append((ligne, nombre))
        for groupe in groupes.values():
            if len(groupe) < 8:
                continue
            quartiles = statistics.quantiles([nombre for _, nombre in groupe], n=4, method="inclusive")
            ecart = quartiles[2] - quartiles[0]
            for ligne, nombre in groupe:
                if nombre < quartiles[0] - coefficient * ecart or nombre > quartiles[2] + coefficient * ecart:
                    ajoute(ligne, col, f"très éloigné des autres meules identiques (la plupart entre {quartiles[0]:.0f} et {quartiles[2]:.0f})", VERIF)

    # 7. doublons
    vus = {}
    for ligne in lignes:
        cle = tuple(str(valeur) for valeur in ligne[1:])                 # toutes les colonnes identiques
        if cle in vus:
            ajoute(ligne, "n° article meule", f"toutes les valeurs sont identiques à la ligne {vus[cle]}", VERIF)
        else:
            vus[cle] = ligne[0]

    out.sort(key=lambda anomalie: (ORDRE[anomalie["gravite"]], anomalie["ligne"]))
    return {"nb_lignes": len(lignes), "anomalies": out}
