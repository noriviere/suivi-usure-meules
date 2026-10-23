"""Jetons de session signés (cookie) et limiteur d'essais de connexion."""
import base64
import hashlib
import hmac
import json
import time


def _b64(octets):
    return base64.urlsafe_b64encode(octets).decode("ascii").rstrip("=")


def _debase(texte_base64):
    return base64.urlsafe_b64decode(texte_base64 + "=" * (-len(texte_base64) % 4))


def _signer(corps, secret):
    return _b64(hmac.new(secret.encode("utf-8"), corps.encode("ascii"), hashlib.sha256).digest())


def creer_jeton(utilisateur_id, version, secret, duree_s, maintenant=None):
    emission = int(maintenant if maintenant is not None else time.time())
    corps = _b64(json.dumps({"u": utilisateur_id, "v": version, "exp": emission + duree_s}).encode("utf-8"))
    return corps + "." + _signer(corps, secret)


def lire_jeton(jeton, secret, maintenant=None):
    """Renvoie {"u": id, "v": version} si le jeton est authentique et non expiré, sinon None."""
    try:
        corps, signature = (jeton or "").split(".")
        if not hmac.compare_digest(signature, _signer(corps, secret)):
            return None
        contenu = json.loads(_debase(corps))
        if contenu["exp"] < (maintenant if maintenant is not None else time.time()):
            return None
        return {"u": int(contenu["u"]), "v": int(contenu["v"])}
    except (ValueError, KeyError, TypeError):
        return None


class Limiteur:
    """Bloque une clé (nom d'utilisateur ou poste) après `maxi` échecs pendant `fenetre_s` secondes."""

    def __init__(self, maxi=5, fenetre_s=300):
        self.maxi, self.fenetre_s, self._echecs = maxi, fenetre_s, {}

    def _recents(self, cle, maintenant):
        recents = [instant for instant in self._echecs.get(cle, []) if maintenant - instant < self.fenetre_s]
        self._echecs[cle] = recents
        return recents

    def bloque(self, cle, maintenant=None):
        return len(self._recents(cle, maintenant if maintenant is not None else time.time())) >= self.maxi

    def echec(self, cle, maintenant=None):
        instant = maintenant if maintenant is not None else time.time()
        self._recents(cle, instant).append(instant)

    def succes(self, cle):
        self._echecs.pop(cle, None)
