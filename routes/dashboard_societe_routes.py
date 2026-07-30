# routes/dashboard_societe_routes.py
from flask import Blueprint, render_template, session
from db import get_db
from utils.decorators import role_requis, societe_requise

dashboard_societe_bp = Blueprint("dashboard_societe", __name__, url_prefix="/mon-dashboard")


@dashboard_societe_bp.route("/")
@role_requis("admin_societe")
@societe_requise
def tableau_de_bord():
    db = get_db()
    id_societe = session["id_societe"]
    
    # Récupérer le nom de la société
    societe = db.execute(
        "SELECT raison_sociale FROM societe WHERE id_societe = ?",
        (id_societe,)
    ).fetchone()
    
    # Statistiques générales
    total_employes = db.execute(
        "SELECT COUNT(*) AS n FROM employe WHERE id_societe = ? AND actif = 1",
        (id_societe,)
    ).fetchone()["n"]
    
    total_employes_inactifs = db.execute(
        "SELECT COUNT(*) AS n FROM employe WHERE id_societe = ? AND actif = 0",
        (id_societe,)
    ).fetchone()["n"]
    
    # Bulletins du mois en cours
    from datetime import datetime
    mois_courant = datetime.now().month
    annee_courante = datetime.now().year
    
    bulletins_mois = db.execute(
        """SELECT COUNT(*) AS n FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ? AND bp.mois = ? AND bp.annee = ?""",
        (id_societe, mois_courant, annee_courante)
    ).fetchone()["n"]
    
    total_bulletins = db.execute(
        """SELECT COUNT(*) AS n FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ?""",
        (id_societe,)
    ).fetchone()["n"]
    
    # Masse salariale du mois
    masse_salariale_mois = db.execute(
        """SELECT COALESCE(SUM(bp.salaire_net_a_payer), 0) AS total 
           FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ? AND bp.mois = ? AND bp.annee = ?""",
        (id_societe, mois_courant, annee_courante)
    ).fetchone()["total"]
    
    # Masse salariale totale
    masse_salariale_totale = db.execute(
        """SELECT COALESCE(SUM(bp.salaire_net_a_payer), 0) AS total 
           FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ?""",
        (id_societe,)
    ).fetchone()["total"]
    
    # Derniers bulletins générés
    derniers_bulletins = db.execute(
        """SELECT bp.*, e.nom, e.prenom, e.matricule
           FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ?
           ORDER BY bp.date_generation DESC
           LIMIT 5""",
        (id_societe,)
    ).fetchall()
    
    # Employés sans bulletin ce mois-ci
    employes_sans_bulletin = db.execute(
        """SELECT e.id_employe, e.nom, e.prenom, e.matricule
           FROM employe e
           WHERE e.id_societe = ? AND e.actif = 1
           AND NOT EXISTS (
               SELECT 1 FROM bulletin_paie bp 
               WHERE bp.id_employe = e.id_employe 
               AND bp.mois = ? AND bp.annee = ?
           )""",
        (id_societe, mois_courant, annee_courante)
    ).fetchall()
    
    return render_template(
        "dashboard_societe/tableau_de_bord.html",
        societe=societe,
        total_employes=total_employes,
        total_employes_inactifs=total_employes_inactifs,
        bulletins_mois=bulletins_mois,
        total_bulletins=total_bulletins,
        masse_salariale_mois=masse_salariale_mois,
        masse_salariale_totale=masse_salariale_totale,
        derniers_bulletins=derniers_bulletins,
        employes_sans_bulletin=employes_sans_bulletin,
        mois_courant=mois_courant,
        annee_courante=annee_courante
    )