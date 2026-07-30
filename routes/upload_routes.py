# routes/upload_routes.py
from flask import Blueprint, request, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
from db import get_db
from utils.decorators import role_requis
import os
import time

upload_bp = Blueprint("upload", __name__, url_prefix="/upload")

UPLOAD_FOLDER = 'static/uploads/logos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}

# Créer le dossier si nécessaire
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_bp.route("/logo", methods=["POST"])
@role_requis("super_admin")
def upload_logo():
    if 'logo' not in request.files:
        flash('Aucun fichier sélectionné.', 'error')
        return redirect(request.referrer or url_for('societe.liste_societes'))
    
    file = request.files['logo']
    if file.filename == '':
        flash('Aucun fichier sélectionné.', 'error')
        return redirect(request.referrer or url_for('societe.liste_societes'))
    
    if not allowed_file(file.filename):
        flash('Format de fichier non accepté. Utilisez PNG, JPG, JPEG, GIF ou SVG.', 'error')
        return redirect(request.referrer or url_for('societe.liste_societes'))
    
    # Sécuriser le nom du fichier
    filename = secure_filename(file.filename)
    # Ajouter un timestamp pour éviter les doublons
    unique_filename = f"{int(time.time())}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(filepath)
    
    # Sauvegarder le chemin dans la base
    db = get_db()
    id_societe = request.form.get('id_societe')
    if id_societe:
        db.execute(
            "UPDATE societe SET logo_path = ? WHERE id_societe = ?",
            (unique_filename, id_societe)
        )
        db.commit()
        flash('✅ Logo téléchargé avec succès !', 'success')
    else:
        flash('ID société manquant.', 'error')
    
    return redirect(request.referrer or url_for('societe.liste_societes'))

from flask import send_from_directory

@upload_bp.route("/logo/<filename>")
def get_logo(filename):
    """Servir le logo de la société"""
    return send_from_directory('uploads/logo', filename)