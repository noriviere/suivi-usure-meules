"""Base SQLite : utilisateurs du back-office, règles métier modifiées, historique des changements."""
import contextlib
import secrets
import sqlite3
import os

from .. import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS utilisateurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE COLLATE NOCASE,
    mdp_hash TEXT NOT NULL,
    version_jeton INTEGER NOT NULL DEFAULT 1,
    cree_le TEXT NOT NULL,
    derniere_connexion TEXT
);
CREATE TABLE IF NOT EXISTS reglages (
    id TEXT PRIMARY KEY,
    actif INTEGER,
    params TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS journal_reglages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    utilisateur TEXT NOT NULL,
    regle TEXT NOT NULL,
    avant TEXT NOT NULL,
    apres TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    cle TEXT PRIMARY KEY,
    valeur TEXT NOT NULL
);
"""


@contextlib.contextmanager
def connexion():
    """Ouvre la base (créée si besoin), valide les changements à la sortie, ferme toujours."""
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def secret_signature():
    """Clé qui signe les cookies de session. Créée au premier appel, gardée dans la base."""
    with connexion() as con:
        ligne = con.execute("SELECT valeur FROM meta WHERE cle = 'secret'").fetchone()
        if ligne:
            return ligne["valeur"]
        secret = secrets.token_hex(32)
        con.execute("INSERT INTO meta (cle, valeur) VALUES ('secret', ?)", (secret,))
        return secret
