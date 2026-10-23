import datetime
import statistics

from .donnees import norm, matricules, lire_data
from .listes import ligne_format, listes_deroulantes
from .valider import cfg, valider


def _matricule(valeur, longueur):
    """'534' -> '0534' (les numéros trop courts sont complétés par des zéros)."""
    texte = str(valeur or "").strip()
    if texte.isdigit() and len(texte) < longueur:
        texte = texte.zfill(longueur)
    return texte


def traiter(donnees):
    """Renvoie (valeurs propres, erreurs bloquantes, avertissements)."""
    copie = dict(donnees)
    listes = listes_deroulantes()
    erreurs, avertissements = [], []

    configuration = cfg()
    champs_matricule = [champ for champ in configuration["champs"] if champ["type"] == "matricule"]
    for champ in champs_matricule:
        if copie.get(champ["nom"]) not in (None, ""):
            copie[champ["nom"]] = _matricule(copie[champ["nom"]], champ.get("longueur", 4))

    ref = None
    if copie.get("Format") and copie.get("Matière"):
        ref = ligne_format(copie["Format"], copie["Matière"])
        if ref is None:
            erreurs.append("Format + Matière : combinaison absente de l'onglet « Formats & matière »")
        else:
            # machines autorisées pour CE format + matière (vide = pas de restriction)
            listes["N° de Machine"] = ref["machines"] or None
            ma5 = norm(ref["ma5"])
            if ma5 in ("oui", "non"):
                copie["MA5"] = ma5.capitalize()            # choisi automatiquement
            elif norm(copie.get("MA5")) in ("oui", "non"):
                copie["MA5"] = norm(copie["MA5"]).capitalize() # « peut-être » : l'utilisateur a choisi
            else:
                erreurs.append("MA5 : la table indique « Peut-être », choisissez Oui ou Non")
    listes["MA5"] = ["Oui", "Non"]

    # Compteur fin à 0 : remplacé par 1 pour ne pas casser les formules Excel (division par le compteur)
    try:
        if str(copie.get("Compteur fin")).strip() != "" and float(str(copie.get("Compteur fin")).replace(",", ".")) == 0:
            copie["Compteur fin"] = 1
            avertissements.append("Compteur fin : 0 a été remplacé par 1 pour ne pas casser les formules Excel.")
    except ValueError:
        pass

    propres, nouvelles_erreurs, nouveaux_avertissements = valider(copie, listes)
    erreurs += nouvelles_erreurs
    avertissements += nouveaux_avertissements

    # Meule différente de celle prévue pour ce format et cette matière
    article = propres.get("N° article meule")
    if configuration["regles"]["meule_non_prevue"] and ref and ref["meules"] and article and article not in ref["meules"]:
        prevues = " / ".join(ref["meules"])
        avertissements.append(
            f"N° article meule : {article} n'est pas la meule prévue pour ce format et cette matière ({prevues})")

    # Matricule jamais utilisé dans le fichier : probablement une faute de frappe
    connus = set(matricules()) if configuration["regles"]["matricule_inconnu"] else set()
    if connus:
        for champ in champs_matricule:
            matricule = propres.get(champ["nom"])
            if matricule and matricule not in connus:
                avertissements.append(f"{champ['nom']} : {matricule} n'a encore jamais été utilisé dans le fichier")

    # Meule non finie : le commentaire est obligatoire
    seuil = configuration.get("seuil_demontee_avant_usure_mm")
    haut_f = propres.get("Hauteur meule finale, mm")
    if (configuration["regles"]["non_fini"] and seuil is not None and haut_f is not None and haut_f > seuil
            and not str(copie.get("Commentaire") or "").strip()):
        erreurs.append(
            f"Commentaire obligatoire : la meule est démontée avant usure totale "
            f"(il reste {haut_f:g} mm). Pourquoi ?")

    avertissements += _hors_habitude(propres)
    doublon = _doublon(propres) if configuration["regles"]["doublon_saisie"] else None
    if doublon:
        avertissements.append(doublon)

    return propres, erreurs, avertissements


# ---------------------------------------------------------------------------
# Valeurs inhabituelles (avertissement seulement, jamais bloquant)
# ---------------------------------------------------------------------------
def _nombres(lignes, colonne):
    out = []
    for ligne in lignes:
        valeur = ligne.get(colonne)
        if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
            out.append(float(valeur))
    return out


def _quartiles(valeurs):
    quartiles = statistics.quantiles(valeurs, n=4, method="inclusive")
    return quartiles[0], quartiles[2]


def _hors_habitude(propres, seulement=None):
    """Compare chaque valeur à l'historique du fichier (règle de Tukey) :
    zone habituelle = [Q1 - k x (Q3-Q1) ; Q3 + k x (Q3-Q1)], k = 1,5.
    Q1 et Q3 : 25 % et 75 % des valeurs déjà saisies, triées.
    Compteur fin : comparé aux saisies de la même meule et de la même matière ;
    les autres champs : à toutes les saisies."""
    cfg_h = cfg().get("controle_habituel") or {}
    coefficient, mini = cfg_h.get("coefficient", 1.5), cfg_h.get("minimum_cas", 20)
    historique = lire_data()
    avert = []
    for nom in (seulement or cfg_h.get("champs", [])):
        valeur = propres.get(nom)
        if valeur is None:
            continue
        base = historique
        portee = "toutes les saisies"
        if nom == "Compteur fin":
            art, mat = propres.get("N° article meule"), propres.get("Matière")
            base = [ligne for ligne in historique
                    if str(ligne.get("n° article meule", "")).strip() == str(art)
                    and norm(ligne.get("matière")) == norm(mat)]
            portee = f"la meule {art} (matière {mat})"
            mini_champ = min(mini, 8)
        else:
            mini_champ = mini
        valeurs = _nombres(base, norm(nom))
        if nom == "Pression d'arrosage":
            if valeur == 0:
                continue                               # 0 = manomètre hors service : normal
            valeurs = [nombre for nombre in valeurs if nombre != 0]
        if len(valeurs) < mini_champ:
            continue                                   # pas assez d'historique pour juger
        q1, q3 = _quartiles(valeurs)
        ecart = q3 - q1
        bas, haut = q1 - coefficient * ecart, q3 + coefficient * ecart
        if valeur < bas or valeur > haut:
            avert.append(
                f"{nom} : {valeur:g} est inhabituel (la plupart des valeurs de {portee} "
                f"sont entre {q1:g} et {q3:g}). Vérifiez la saisie.")
    return avert


# ---------------------------------------------------------------------------
# Saisie identique à une saisie existante
# ---------------------------------------------------------------------------
def _jour(valeur):
    if isinstance(valeur, (datetime.datetime, datetime.date)):
        return valeur.strftime("%Y-%m-%d")
    return str(valeur)[:10]


def _doublon(propres):
    cles = {
        "n° article meule": str(propres.get("N° article meule", "")),
        "n° de machine": str(propres.get("N° de Machine", "")),
        "face": str(propres.get("Face", "")),
        "date montage": _jour(propres.get("Date montage", "")),
        "compteur fin": propres.get("Compteur fin"),
    }
    if any(valeur in (None, "") for valeur in cles.values()):
        return None
    for ligne in lire_data():
        ok = (str(ligne.get("n° article meule", "")).strip() == cles["n° article meule"]
              and norm(ligne.get("n° de machine")) == norm(cles["n° de machine"])
              and norm(ligne.get("face")) == norm(cles["face"])
              and _jour(ligne.get("date montage")) == cles["date montage"]
              and isinstance(ligne.get("compteur fin"), (int, float))
              and float(ligne["compteur fin"]) == float(cles["compteur fin"]))
        if ok:
            return (f"Une saisie identique existe déjà dans le fichier (meule {cles['n° article meule']}, "
                    f"face {cles['face']}, machine {cles['n° de machine']}, "
                    f"montage du {cles['date montage'][8:10]}/{cles['date montage'][5:7]}/{cles['date montage'][:4]}, "
                    f"compteur fin {cles['compteur fin']:g}). Est-ce un doublon ?")
    return None


# ---------------------------------------------------------------------------
# Meule cassée et non finie : copie dans l'onglet des meules défectueuses
# ---------------------------------------------------------------------------
def vers_defaut(propres):
    configuration = cfg()
    defaut = configuration.get("defaut")
    seuil = configuration.get("seuil_demontee_avant_usure_mm")
    hauteur = propres.get("Hauteur meule finale, mm")
    com = str(propres.get("Commentaire") or "")
    return bool(defaut and seuil is not None and hauteur is not None and hauteur > seuil
                and defaut["theme"] in com)


def verifier_champ(nom, valeur, article=None, matiere=None):
    """Contrôle « hors habitude » d'un seul champ, pour la page de saisie (en direct).
    Renvoie le texte de l'avertissement, ou "" si tout est normal."""
    try:
        nombre = float(str(valeur).replace(",", "."))
    except ValueError:
        return ""
    if nom not in (cfg().get("controle_habituel") or {}).get("champs", []):
        return ""
    resultat = _hors_habitude({nom: nombre, "N° article meule": article, "Matière": matiere}, [nom])
    return resultat[0] if resultat else ""


def perte_annuelle(annee=None):
    """Valeur (en €) de la meule non utilisée sur les meules démontées avant 0 mm, pour l'année en cours :
    pour chaque ligne, hauteur finale / hauteur initiale x prix moyen d'une meule."""
    annee = annee or datetime.date.today().year
    prix = cfg().get("prix_meule_moyenne_eur", 150)
    total, nb = 0.0, 0
    for ligne in lire_data():
        date_montage = ligne.get("date montage")
        if not isinstance(date_montage, (datetime.datetime, datetime.date)) or date_montage.year != annee:
            continue
        hi, hf = ligne.get("hauteur meule initiale, mm"), ligne.get("hauteur meule finale, mm")
        if isinstance(hi, (int, float)) and isinstance(hf, (int, float)) and hi > 0 and hf > 0:
            total += min(hf, hi) / hi * prix
            nb += 1
    return {"annee": annee, "total": round(total, 2), "nb": nb, "prix": prix}
