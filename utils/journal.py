"""
Petite fonction utilitaire pour enregistrer une action dans la table
journal_action (traçabilité des actions des utilisateurs).
"""
from flask import session


def enregistrer_action(db, action, details=""):
    db.execute(
        "INSERT INTO journal_action (id_utilisateur, id_societe, action, details) VALUES (?, ?, ?, ?)",
        (session.get("id_utilisateur"), session.get("id_societe"), action, details),
    )
    db.commit()