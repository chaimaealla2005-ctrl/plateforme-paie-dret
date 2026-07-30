from flask import Blueprint, render_template
from db import get_db
from utils.decorators import role_requis

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@role_requis("super_admin")
def tableau_de_bord():
    db = get_db()

    nb_actives = db.execute("SELECT COUNT(*) AS n FROM societe WHERE actif = 1").fetchone()["n"]
    nb_inactives = db.execute("SELECT COUNT(*) AS n FROM societe WHERE actif = 0").fetchone()["n"]

    stats = {
        "nb_societes": nb_actives,
        "nb_societes_inactives": nb_inactives,
        "nb_employes": db.execute("SELECT COUNT(*) AS n FROM employe WHERE actif = 1").fetchone()["n"],
        "nb_bulletins": db.execute("SELECT COUNT(*) AS n FROM bulletin_paie").fetchone()["n"],
        "masse_salariale": db.execute(
            "SELECT COALESCE(SUM(salaire_net_a_payer), 0) AS total FROM bulletin_paie"
        ).fetchone()["total"],
    }

    par_societe = db.execute(
        """SELECT s.raison_sociale,
                  (SELECT COUNT(*) FROM employe e WHERE e.id_societe = s.id_societe AND e.actif = 1) AS nb_employes,
                  (SELECT COUNT(*) FROM bulletin_paie bp
                     JOIN employe e2 ON e2.id_employe = bp.id_employe
                     WHERE e2.id_societe = s.id_societe) AS nb_bulletins,
                  (SELECT COALESCE(SUM(bp.salaire_net_a_payer), 0) FROM bulletin_paie bp
                     JOIN employe e3 ON e3.id_employe = bp.id_employe
                     WHERE e3.id_societe = s.id_societe) AS masse_salariale
           FROM societe s
           ORDER BY s.raison_sociale"""
    ).fetchall()

    return render_template("dashboard/tableau_de_bord.html", stats=stats, par_societe=par_societe)


@dashboard_bp.route("/employes")
@role_requis("super_admin")
def tous_les_employes():
    db = get_db()
    employes = db.execute(
        """SELECT e.*, s.raison_sociale
           FROM employe e
           JOIN societe s ON s.id_societe = e.id_societe
           WHERE e.actif = 1
           ORDER BY s.raison_sociale, e.nom"""
    ).fetchall()
    return render_template("dashboard/tous_employes.html", employes=employes)


@dashboard_bp.route("/bulletins")
@role_requis("super_admin")
def tous_les_bulletins():
    db = get_db()
    bulletins = db.execute(
        """SELECT bp.*, e.nom, e.prenom, s.raison_sociale
           FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           JOIN societe s ON s.id_societe = e.id_societe
           ORDER BY bp.annee DESC, bp.mois DESC"""
    ).fetchall()
    return render_template("dashboard/tous_bulletins.html", bulletins=bulletins)


@dashboard_bp.route("/journal")
@role_requis("super_admin")
def journal():
    db = get_db()
    actions = db.execute(
        """SELECT j.*, u.email, s.raison_sociale
           FROM journal_action j
           LEFT JOIN utilisateur u ON u.id_utilisateur = j.id_utilisateur
           LEFT JOIN societe s ON s.id_societe = j.id_societe
           ORDER BY j.date_action DESC
           LIMIT 200"""
    ).fetchall()
    return render_template("dashboard/journal.html", actions=actions)