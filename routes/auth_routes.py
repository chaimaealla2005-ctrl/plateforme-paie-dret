# routes/auth_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db
from utils.decorators import role_requis
from utils.journal import enregistrer_action
import re

auth_bp = Blueprint("auth", __name__, url_prefix="")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        mot_de_passe = request.form["mot_de_passe"]

        db = get_db()
        utilisateur = db.execute(
            "SELECT * FROM utilisateur WHERE lower(email) = ? AND actif = 1",
            (email,),
        ).fetchone()

        if utilisateur is None or not check_password_hash(utilisateur["mot_de_passe_hash"], mot_de_passe):
            flash("Email ou mot de passe incorrect.", "error")
            return redirect(url_for("auth.login"))

        # On enregistre les infos utiles dans la session (cote serveur, securise)
        session.clear()
        session["id_utilisateur"] = utilisateur["id_utilisateur"]
        session["role"] = utilisateur["role"]
        session["id_societe"] = utilisateur["id_societe"]
        session["nom"] = f"{utilisateur['prenom']} {utilisateur['nom']}"

        flash(f"Bienvenue, {session['nom']} !", "success")

        if utilisateur["role"] == "super_admin":
            return redirect(url_for("dashboard.tableau_de_bord"))
        elif utilisateur["role"] == "admin_societe":
            return redirect(url_for("dashboard_societe.tableau_de_bord"))
        elif utilisateur["role"] == "employe":
            return redirect(url_for("bulletin.mon_bulletin"))
        else:
            return redirect(url_for("employe.liste_employes"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Vous êtes déconnecté.", "success")
    return redirect(url_for("auth.login"))

# ============================================================
# CHANGER LE MOT DE PASSE (après connexion)
# ============================================================
@auth_bp.route("/changer-mot-de-passe", methods=["GET", "POST"])
@role_requis("super_admin", "admin_societe", "rh", "comptable", "employe")
def changer_mot_de_passe():
    """Permet à l'utilisateur connecté de changer son mot de passe"""
    
    if request.method == "POST":
        ancien_mot_de_passe = request.form.get("ancien_mot_de_passe")
        nouveau_mot_de_passe = request.form.get("nouveau_mot_de_passe")
        confirmation = request.form.get("confirmation")
        
        # Vérifier que tous les champs sont remplis
        if not ancien_mot_de_passe or not nouveau_mot_de_passe or not confirmation:
            flash("Tous les champs sont obligatoires.", "error")
            return render_template("auth/changer_mot_de_passe.html")
        
        # Vérifier que le nouveau mot de passe et la confirmation correspondent
        if nouveau_mot_de_passe != confirmation:
            flash("Les nouveaux mots de passe ne correspondent pas.", "error")
            return render_template("auth/changer_mot_de_passe.html")
        
        # Vérifier la longueur du mot de passe
        if len(nouveau_mot_de_passe) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
            return render_template("auth/changer_mot_de_passe.html")
        
        db = get_db()
        
        # Récupérer l'utilisateur
        utilisateur = db.execute(
            "SELECT * FROM utilisateur WHERE id_utilisateur = ?",
            (session["id_utilisateur"],)
        ).fetchone()
        
        if utilisateur is None:
            flash("Utilisateur introuvable.", "error")
            return redirect(url_for("auth.login"))
        
        # Vérifier l'ancien mot de passe
        if not check_password_hash(utilisateur["mot_de_passe_hash"], ancien_mot_de_passe):
            flash("L'ancien mot de passe est incorrect.", "error")
            return render_template("auth/changer_mot_de_passe.html")
        
        # Mettre à jour le mot de passe
        nouveau_hash = generate_password_hash(nouveau_mot_de_passe)
        db.execute(
            "UPDATE utilisateur SET mot_de_passe_hash = ? WHERE id_utilisateur = ?",
            (nouveau_hash, session["id_utilisateur"])
        )
        db.commit()
        
        enregistrer_action(db, "changement_mot_de_passe", f"Mot de passe modifié pour {utilisateur['email']}")
        
        flash("✅ Votre mot de passe a été modifié avec succès.", "success")
        return redirect(url_for("auth.logout"))  # Déconnecter pour forcer la reconnexion avec le nouveau mot de passe
    
    return render_template("auth/changer_mot_de_passe.html")