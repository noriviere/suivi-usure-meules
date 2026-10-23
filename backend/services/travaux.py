"""Travaux de fond : l'enregistrement dans Excel dure plusieurs secondes. La route le lance dans un fil
et rend un identifiant ; la page interroge ensuite l'avancement (étape en cours, puis résultat)."""
import threading
import time
import uuid

_travaux = {}
_verrou = threading.Lock()
CONSERVATION_S = 600           # un travail terminé reste consultable 10 minutes


def lancer(fonction):
    """fonction(progression) -> (statut http, corps). `progression(etape)` note l'étape en cours.
    Renvoie l'identifiant du travail."""
    identifiant = uuid.uuid4().hex
    maintenant = time.time()
    with _verrou:
        for cle in [cle for cle, travail in _travaux.items() if travail["fini"] and maintenant - travail["fin"] > CONSERVATION_S]:
            del _travaux[cle]
        _travaux[identifiant] = {"etape": "attente", "fini": False, "statut": None, "corps": None, "fin": None}

    def progression(etape):
        with _verrou:
            _travaux[identifiant]["etape"] = etape

    def executer():
        try:
            statut, corps = fonction(progression)
        except Exception as erreur:                                  # filet de sécurité : jamais de travail bloqué
            statut, corps = 500, {"erreurs": [f"Écriture impossible : {erreur}"], "avertissements": []}
        with _verrou:
            _travaux[identifiant].update(fini=True, statut=statut, corps=corps, fin=time.time(), etape="termine")

    threading.Thread(target=executer, daemon=True).start()
    return identifiant


def lire(identifiant):
    """Copie de l'état d'un travail, ou None s'il est inconnu."""
    with _verrou:
        travail = _travaux.get(identifiant)
        return dict(travail) if travail else None
