# app.py
from flask import Flask, redirect, url_for, session
from flask_mail import Mail
import os

import db as db_module
from seed_demo import creer_donnees_demo

from routes.auth_routes import auth_bp
from routes.societe_routes import societe_bp
from routes.employe_routes import employe_bp
from routes.element_paie_routes import element_bp
from routes.bulletin_routes import bulletin_bp
from routes.utilisateur_routes import utilisateur_bp
from routes.dashboard_routes import dashboard_bp
from routes.parametrage_routes import parametrage_bp
from routes.parametrage_societe_routes import parametrage_societe_bp
from routes.dashboard_societe_routes import dashboard_societe_bp
from routes.conge_routes import conge_bp
from routes.notification_parametres_routes import notification_parametres_bp
from routes.personnel_routes import personnel_bp
from routes.historique_routes import historique_bp



def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    
    # Initialiser Flask-Mail
    mail = Mail(app)
    
    # Stocker mail dans app pour y accéder dans les routes
    app.mail = mail
    
    db_module.init_app(app)
    
    # Enregistrement des blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(societe_bp)
    app.register_blueprint(employe_bp)
    app.register_blueprint(element_bp)
    app.register_blueprint(bulletin_bp)
    app.register_blueprint(utilisateur_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(parametrage_bp)
    app.register_blueprint(parametrage_societe_bp)
    app.register_blueprint(dashboard_societe_bp)
    app.register_blueprint(conge_bp)
    app.register_blueprint(notification_parametres_bp)
    app.register_blueprint(personnel_bp)
    app.register_blueprint(historique_bp)
    
    @app.route("/")
    def index():
        if "id_utilisateur" not in session:
            return redirect(url_for("auth.login"))
        if session["role"] == "super_admin":
            return redirect(url_for("dashboard.tableau_de_bord"))
        if session["role"] == "admin_societe":
            return redirect(url_for("dashboard_societe.tableau_de_bord"))
        if session["role"] == "employe":
            return redirect(url_for("bulletin.mon_bulletin"))
        return redirect(url_for("employe.liste_employes"))
    
    with app.app_context():
        premiere_installation = not os.path.exists(app.config["DATABASE"])
        if premiere_installation:
            db_module.init_db()
            db = db_module.get_db()
            creer_donnees_demo(db)
            print(">> Base de donnees creee avec les comptes de demonstration.")
    
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)