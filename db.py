"""
Gestion de la connexion a la base de donnees SQLite.
Utilise le module sqlite3 standard de Python (aucune dependance
supplementaire a installer).
"""
import sqlite3
from flask import g, current_app


def get_db():
    """Retourne la connexion a la base de donnees pour la requete en cours.
    Reutilise la meme connexion tout au long d'une requete Flask (via 'g')."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # permet d'acceder aux colonnes par nom (row['nom'])
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Ferme la connexion a la fin de la requete."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Cree les tables (schema.sql) et charge la loi marocaine (seed_loi_marocaine.sql)."""
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf8"))
    with current_app.open_resource("seed_loi_marocaine.sql") as f:
        db.executescript(f.read().decode("utf8"))
    db.commit()


def init_app(app):
    """A appeler une fois au demarrage de l'application (voir app.py)."""
    app.teardown_appcontext(close_db)