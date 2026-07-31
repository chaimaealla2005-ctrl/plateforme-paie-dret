# db.py
import sqlite3
from flask import g, current_app


def get_db():
    """Retourne la connexion à la base de données pour la requête en cours."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Ferme la connexion à la fin de la requête."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Crée les tables (schema.sql) et charge la loi marocaine (seed_loi_marocaine.sql)."""
    db = get_db()
    
    # Exécuter schema.sql en ignorant les erreurs de colonnes dupliquées
    with current_app.open_resource("schema.sql") as f:
        sql = f.read().decode("utf8")
        for statement in sql.split(';'):
            stmt = statement.strip()
            if stmt:
                try:
                    db.execute(stmt)
                except sqlite3.OperationalError as e:
                    if 'duplicate column name' in str(e) or 'already exists' in str(e):
                        pass  # Ignorer les colonnes déjà existantes
                    else:
                        print(f"⚠️ Erreur: {e}")
    
    # Charger les données légales
    with current_app.open_resource("seed_loi_marocaine.sql") as f:
        try:
            db.executescript(f.read().decode("utf8"))
        except sqlite3.OperationalError as e:
            print(f"⚠️ Erreur seed: {e}")
    
    db.commit()


def init_app(app):
    """A appeler une fois au demarrage de l'application."""
    app.teardown_appcontext(close_db)