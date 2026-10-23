"""Règles métier modifiables depuis le back-office.
Les valeurs d'origine sont dans config/champs.json ; les changements sont gardés dans la base SQLite
(table reglages) avec un historique (table journal_reglages)."""
import copy
import datetime
import json

from .. import config as cfg_app
from ..auth import db

with open(cfg_app.CHAMPS_JSON, encoding="utf-8") as fichier:
    BASE = json.load(fichier)

_cache = {"cle": None, "config": None}


def _p(cle, libelle, defaut, mini, maxi, unite="", pas=1):
    return {"cle": cle, "libelle": libelle, "defaut": defaut, "min": mini, "max": maxi, "unite": unite, "pas": pas}


def _champ(nom):
    return next(champ for champ in BASE["champs"] if champ["nom"] == nom)


# Liste des règles : id, groupe, titre, aide, interrupteur (None = règle toujours active), paramètres
REGLES = [
    {"id": "non_fini", "groupe": "Démontage", "titre": "Meule démontée avant usure totale",
     "aide": "Si la hauteur finale dépasse ce seuil, la meule est marquée X. Interrupteur : exiger ou non une explication dans le commentaire.",
     "switch": True, "params": [_p("seuil", "Seuil de hauteur finale", BASE["seuil_demontee_avant_usure_mm"], 0, 30, "mm", 0.5)]},
    {"id": "rotation_max", "groupe": "Limites bloquantes", "titre": "Vitesse de rotation maximale",
     "aide": "Au-delà, la saisie est refusée.", "switch": True,
     "params": [_p("valeur", "Maximum", _champ("Vitesse de rotation").get("max", 50), 1, 1000, "m/s")]},
    {"id": "avance_max", "groupe": "Limites bloquantes", "titre": "Vitesse d'avance maximale",
     "aide": "Au-delà, la saisie est refusée.", "switch": True,
     "params": [_p("valeur", "Maximum", _champ("V.Avance").get("max", 1000), 1, 100000, "mm/min")]},
    {"id": "hauteur_init_max", "groupe": "Limites bloquantes", "titre": "Hauteur initiale maximale (meule neuve)",
     "aide": "Au-delà, la saisie est refusée.", "switch": True,
     "params": [_p("valeur", "Maximum", _champ("Hauteur meule initiale, mm").get("max", 110), 1, 1000, "mm")]},
    {"id": "hors_habitude", "groupe": "Avertissements (non bloquants)", "titre": "Valeur inhabituelle par rapport à l'historique",
     "aide": "Pression, vitesse, avance, hauteur initiale et compteur fin sont comparés aux saisies passées. Plus le coefficient est petit, plus on signale de valeurs.",
     "switch": True,
     "params": [_p("coefficient", "Coefficient", BASE["controle_habituel"]["coefficient"], 0.5, 6, "", 0.1),
                _p("minimum_cas", "Historique minimum", BASE["controle_habituel"]["minimum_cas"], 5, 500, "saisies")]},
    {"id": "doublon_saisie", "groupe": "Avertissements (non bloquants)", "titre": "Saisie identique à une saisie existante",
     "aide": "Même meule, machine, face, date de montage et compteur fin.", "switch": True, "params": []},
    {"id": "matricule_inconnu", "groupe": "Avertissements (non bloquants)", "titre": "Matricule jamais utilisé dans le fichier",
     "aide": "Repère les fautes de frappe sur les matricules.", "switch": True, "params": []},
    {"id": "meule_non_prevue", "groupe": "Avertissements (non bloquants)", "titre": "Meule différente de celle prévue pour le format",
     "aide": "Compare la meule saisie à celle du tableau « Formats & matière ».", "switch": True, "params": []},
    {"id": "date_futur", "groupe": "Avertissements (non bloquants)", "titre": "Date de montage dans le futur",
     "aide": "", "switch": True, "params": []},
    {"id": "machine_non_prevue", "groupe": "Démontage", "titre": "Machine non prévue pour ce format",
     "aide": "Actif : avertissement et commentaire obligatoire. Inactif : toute machine est acceptée sans question.",
     "switch": True, "params": []},
    {"id": "controle_eloigne", "groupe": "Contrôle qualité (consultation)", "titre": "Durée de vie très éloignée des meules identiques",
     "aide": "Plus le coefficient est grand, moins de lignes sont signalées.", "switch": True,
     "params": [_p("coefficient", "Coefficient", BASE["controle_qualite"]["coefficient_eloigne"], 1, 10, "", 0.5)]},
    {"id": "prix_meule", "groupe": "Calculs", "titre": "Prix d'une meule moyenne",
     "aide": "Sert à estimer les euros perdus quand une meule n'est pas finie.", "switch": False,
     "params": [_p("valeur", "Prix", BASE["prix_meule_moyenne_eur"], 1, 100000, "€", 1)]},
]
PAR_ID = {regle["id"]: regle for regle in REGLES}


def lire():
    """Changements enregistrés : {id: {"actif": bool, "params": {...}}}."""
    with db.connexion() as con:
        lignes = con.execute("SELECT id, actif, params FROM reglages").fetchall()
    out = {}
    for ligne in lignes:
        reglage = {"params": json.loads(ligne["params"] or "{}")}
        if ligne["actif"] is not None:
            reglage["actif"] = bool(ligne["actif"])
        out[ligne["id"]] = reglage
    return out


def _valeurs(ov):
    """Pour chaque règle : (actif, {param: valeur}) en tenant compte des valeurs par défaut."""
    out = {}
    for regle in REGLES:
        reglage = ov.get(regle["id"]) or {}
        actif = bool(reglage.get("actif", True)) if regle["switch"] else True
        params = {}
        for parametre in regle["params"]:
            valeur = (reglage.get("params") or {}).get(parametre["cle"], parametre["defaut"])
            params[parametre["cle"]] = valeur if isinstance(valeur, (int, float)) and not isinstance(valeur, bool) else parametre["defaut"]
        out[regle["id"]] = (actif, params)
    return out


def _construire(ov):
    configuration = copy.deepcopy(BASE)
    valeurs_regles = _valeurs(ov)
    configuration["regles"] = {identifiant: actif for identifiant, (actif, _) in valeurs_regles.items()}

    configuration["seuil_demontee_avant_usure_mm"] = valeurs_regles["non_fini"][1]["seuil"]
    for rid, nom in (("rotation_max", "Vitesse de rotation"), ("avance_max", "V.Avance"),
                     ("hauteur_init_max", "Hauteur meule initiale, mm")):
        champ = next(candidat for candidat in configuration["champs"] if candidat["nom"] == nom)
        if valeurs_regles[rid][0]:
            champ["max"] = valeurs_regles[rid][1]["valeur"]
        else:
            champ.pop("max", None)
    ch = configuration["controle_habituel"]
    ch["coefficient"], ch["minimum_cas"] = valeurs_regles["hors_habitude"][1]["coefficient"], valeurs_regles["hors_habitude"][1]["minimum_cas"]
    if not valeurs_regles["hors_habitude"][0]:
        ch["champs"] = []
    if not valeurs_regles["machine_non_prevue"][0]:
        next(champ for champ in configuration["champs"] if champ["nom"] == "N° de Machine")["hors_liste"] = "ignorer"
    configuration["controle_qualite"]["coefficient_eloigne"] = valeurs_regles["controle_eloigne"][1]["coefficient"]
    configuration["prix_meule_moyenne_eur"] = valeurs_regles["prix_meule"][1]["valeur"]
    return configuration


def config():
    """Configuration en vigueur : champs.json + changements enregistrés dans la base."""
    ov = lire()
    cle = json.dumps(ov, sort_keys=True)
    if _cache["cle"] != cle:
        _cache.update(cle=cle, config=_construire(ov))
    return _cache["config"]


def etat():
    """Pour la page : règles, interrupteurs, valeurs en vigueur."""
    ov = lire()
    valeurs_regles = _valeurs(ov)
    out = []
    for regle in REGLES:
        actif, params = valeurs_regles[regle["id"]]
        out.append({**{cle: regle[cle] for cle in ("id", "groupe", "titre", "aide", "switch")}, "actif": actif,
                    "params": [{**parametre, "valeur": params[parametre["cle"]]} for parametre in regle["params"]]})
    return {"regles": out, "modifie": bool(ov)}


def verifier_demande(demande):
    """Contrôle la demande de la page. Renvoie (réglages à enregistrer, erreurs)."""
    erreurs, nouveau = [], {}
    for rid, reglage in (demande or {}).items():
        regle = PAR_ID.get(rid)
        if not regle or not isinstance(reglage, dict):
            erreurs.append(f"Règle inconnue : {rid}")
            continue
        entree = {}
        if regle["switch"]:
            entree["actif"] = bool(reglage.get("actif", True))
        params = {}
        for parametre in regle["params"]:
            brut = (reglage.get("params") or {}).get(parametre["cle"], parametre["defaut"])
            try:
                if isinstance(brut, bool):
                    raise ValueError
                nombre = float(str(brut).replace(",", "."))
                if not (parametre["min"] <= nombre <= parametre["max"]):
                    erreurs.append(f"{regle['titre']} ({parametre['libelle']}) : entre {parametre['min']:g} et {parametre['max']:g} {parametre['unite']}".strip())
                    continue
            except ValueError:
                erreurs.append(f"{regle['titre']} ({parametre['libelle']}) : nombre invalide")
                continue
            params[parametre["cle"]] = int(nombre) if nombre.is_integer() else nombre
        if params:
            entree["params"] = params
        nouveau[rid] = entree
    return nouveau, erreurs


def _txt(va):
    actif, params = va
    return ("actif" if actif else "désactivé") + "".join(f" · {cle}={valeur:g}" for cle, valeur in params.items())


def enregistrer(demande, utilisateur):
    """Enregistre les règles envoyées par la page et note chaque changement. Renvoie la liste des erreurs."""
    nouveau, erreurs = verifier_demande(demande)
    if erreurs:
        return erreurs
    avant = _valeurs(lire())
    apres = _valeurs(nouveau)
    maintenant = datetime.datetime.now().isoformat(timespec="seconds")
    with db.connexion() as con:
        con.execute("DELETE FROM reglages")
        for rid, reglage in nouveau.items():
            con.execute("INSERT INTO reglages (id, actif, params) VALUES (?, ?, ?)",
                        (rid, (1 if reglage["actif"] else 0) if "actif" in reglage else None, json.dumps(reglage.get("params", {}))))
        for regle in REGLES:
            if avant[regle["id"]] != apres[regle["id"]]:
                con.execute("INSERT INTO journal_reglages (date, utilisateur, regle, avant, apres) VALUES (?, ?, ?, ?, ?)",
                            (maintenant, utilisateur, regle["titre"], _txt(avant[regle["id"]]), _txt(apres[regle["id"]])))
    return []


def reinitialiser(utilisateur):
    """Revient aux valeurs d'origine de champs.json."""
    maintenant = datetime.datetime.now().isoformat(timespec="seconds")
    with db.connexion() as con:
        con.execute("DELETE FROM reglages")
        con.execute("INSERT INTO journal_reglages (date, utilisateur, regle, avant, apres) VALUES (?, ?, ?, ?, ?)",
                    (maintenant, utilisateur, "Toutes les règles", "", "valeurs d'origine"))


def historique(limite=100):
    with db.connexion() as con:
        return [dict(ligne) for ligne in con.execute(
            "SELECT date, utilisateur, regle, avant, apres FROM journal_reglages ORDER BY id DESC LIMIT ?", (limite,))]


# ---- affichage de la page de saisie (pas une règle de vérification) ------------------
def affichage():
    """Réglages d'apparence lus par la page de saisie (sans connexion)."""
    with db.connexion() as con:
        ligne = con.execute("SELECT valeur FROM meta WHERE cle = 'humour'").fetchone()
    return {"humour": bool(ligne) and ligne["valeur"] == "1"}


def definir_humour(actif, utilisateur):
    """Active ou coupe les messages humoristiques de la barre d'enregistrement. Le changement est noté dans l'historique."""
    actif = bool(actif)
    avant = affichage()["humour"]
    with db.connexion() as con:
        con.execute("INSERT INTO meta (cle, valeur) VALUES ('humour', ?) "
                    "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur", ("1" if actif else "0",))
        if avant != actif:
            con.execute("INSERT INTO journal_reglages (date, utilisateur, regle, avant, apres) VALUES (?, ?, ?, ?, ?)",
                        (datetime.datetime.now().isoformat(timespec="seconds"), utilisateur,
                         "Messages humoristiques à l'enregistrement",
                         "oui" if avant else "non", "oui" if actif else "non"))
    return actif
