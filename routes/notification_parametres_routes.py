# routes/notification_parametres_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
from utils.decorators import role_requis

notification_parametres_bp = Blueprint("notification_parametres", __name__, url_prefix="/parametres-notifications")


@notification_parametres_bp.route("/")
@role_requis("super_admin")
def vue_ensemble():
    db = get_db()
    parametres = db.execute("SELECT * FROM parametre_notification ORDER BY code").fetchall()
    return render_template("parametres_notifications/vue_ensemble.html", parametres=parametres)


@notification_parametres_bp.route("/modifier", methods=["POST"])
@role_requis("super_admin")
def modifier():
    db = get_db()
    
    for code, valeur in request.form.items():
        if code.startswith('param_'):
            code_reel = code.replace('param_', '')
            db.execute(
                "UPDATE parametre_notification SET valeur = ? WHERE code = ?",
                (valeur.strip(), code_reel)
            )
    
    db.commit()
    flash("✅ Paramètres de notification mis à jour avec succès.", "success")
    return redirect(url_for("notification_parametres.vue_ensemble"))