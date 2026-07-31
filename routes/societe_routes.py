# routes/societe_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from db import get_db
from utils.decorators import role_requis
from utils.journal import enregistrer_action
from werkzeug.utils import secure_filename
import os
import time
import math
from utils.pagination import Pagination
import csv
import io
from utils.export import export_societes, export_to_csv, export_to_excel

societe_bp = Blueprint("societe", __name__, url_prefix="/societes")

# Configuration pour l'upload de logos
UPLOAD_FOLDER = 'uploads/logo'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 Mo

# Créer le dossier si nécessaire
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@societe_bp.route("/nouvelle", methods=["GET", "POST"])
@role_requis("super_admin")
def nouvelle_societe():
    if request.method == "POST":
        db = get_db()
        
        # Gérer l'upload du logo
        logo_path = ""
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename:
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{int(time.time())}_{filename}"
                    file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                    logo_path = unique_filename
                    print(f"✅ Logo uploadé: {logo_path}")  # DEBUG
        
        db.execute(
            """INSERT INTO societe 
               (raison_sociale, ice, adresse, cnss, rc, mode_paiement, logo_path) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                request.form["raison_sociale"],
                request.form.get("ice", ""),
                request.form.get("adresse", ""),
                request.form.get("cnss", ""),
                request.form.get("rc", ""),
                request.form.get("mode_paiement", "Virement bancaire / Chèque"),
                logo_path
            )
        )
        id_societe = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.commit()
        flash("Société créée avec succès.", "success")
        return redirect(url_for("societe.liste_societes"))
    
    return render_template("societes/formulaire.html", societe=None)


@societe_bp.route("/<int:id_societe>/modifier", methods=["GET", "POST"])
@role_requis("super_admin")
def modifier_societe(id_societe):
    db = get_db()
    societe = db.execute("SELECT * FROM societe WHERE id_societe = ?", (id_societe,)).fetchone()
    if societe is None:
        flash("Société introuvable.", "error")
        return redirect(url_for("societe.liste_societes"))

    if request.method == "POST":
        # Gérer l'upload du logo
        logo_path = societe["logo_path"] or ""
        
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename:
                if allowed_file(file.filename):
                    # Supprimer l'ancien logo si existant
                    if logo_path:
                        old_path = os.path.join(UPLOAD_FOLDER, logo_path)
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    filename = secure_filename(file.filename)
                    unique_filename = f"{int(time.time())}_{filename}"
                    file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                    logo_path = unique_filename
                    print(f"✅ Nouveau logo uploadé: {logo_path}")  # DEBUG
        
        db.execute(
            """UPDATE societe 
               SET raison_sociale = ?, ice = ?, adresse = ?, cnss = ?, rc = ?, 
                   mode_paiement = ?, logo_path = ?
               WHERE id_societe = ?""",
            (
                request.form["raison_sociale"],
                request.form.get("ice", ""),
                request.form.get("adresse", ""),
                request.form.get("cnss", ""),
                request.form.get("rc", ""),
                request.form.get("mode_paiement", "Virement bancaire / Chèque"),
                logo_path,
                id_societe
            )
        )
        db.commit()
        flash("Société mise à jour.", "success")
        return redirect(url_for("societe.liste_societes"))

    return render_template("societes/formulaire.html", societe=societe)


@societe_bp.route("/export")
@role_requis("super_admin")
def export_societes_csv():
    """Exporter la liste des sociétés en CSV/Excel"""
    db = get_db()
    
    # Récupérer les sociétés
    societes = db.execute(
        """SELECT s.*,
                  (SELECT COUNT(*) FROM employe e WHERE e.id_societe = s.id_societe AND e.actif = 1) AS nb_employes,
                  (SELECT COUNT(*) FROM utilisateur u WHERE u.id_societe = s.id_societe) AS nb_utilisateurs
           FROM societe s
           ORDER BY s.raison_sociale"""
    ).fetchall()
    
    # Préparer les données
    headers, data = export_societes(societes)
    
    # Choisir le format
    format_type = request.args.get('format', 'csv')
    
    if format_type == 'excel':
        return export_to_excel(data, headers, 'societes')
    else:
        return export_to_csv(data, headers, 'societes')

# routes/societe_routes.py - Modifier la fonction liste_societes

@societe_bp.route("/")
@role_requis("super_admin")
def liste_societes():
    db = get_db()
    
    # Récupérer les paramètres de pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if per_page > 100:
        per_page = 100
    
    # Récupérer les paramètres de filtrage
    filtre_recherche = request.args.get('recherche', '').strip()
    filtre_statut = request.args.get('statut', 'tous')
    filtre_employes_min = request.args.get('employes_min', '').strip()
    filtre_employes_max = request.args.get('employes_max', '').strip()
    
    # Construction de la requête
    query = """
        SELECT s.*,
               (SELECT COUNT(*) FROM employe e WHERE e.id_societe = s.id_societe AND e.actif = 1) AS nb_employes,
               (SELECT COUNT(*) FROM utilisateur u WHERE u.id_societe = s.id_societe) AS nb_utilisateurs
        FROM societe s
        WHERE 1=1
    """
    count_query = "SELECT COUNT(*) AS total FROM societe s WHERE 1=1"
    params = []
    count_params = []
    
    if filtre_recherche:
        query += " AND (s.raison_sociale LIKE ? OR s.ice LIKE ?)"
        params.append(f'%{filtre_recherche}%')
        params.append(f'%{filtre_recherche}%')
        count_query += " AND (s.raison_sociale LIKE ? OR s.ice LIKE ?)"
        count_params.append(f'%{filtre_recherche}%')
        count_params.append(f'%{filtre_recherche}%')
    
    if filtre_statut == 'actif':
        query += " AND s.actif = 1"
        count_query += " AND s.actif = 1"
    elif filtre_statut == 'inactif':
        query += " AND s.actif = 0"
        count_query += " AND s.actif = 0"
    
    # Obtenir le nombre total
    total = db.execute(count_query, count_params).fetchone()["total"]
    
    # Pagination
    offset = (page - 1) * per_page
    query += " ORDER BY s.raison_sociale LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    societes = db.execute(query, params).fetchall()
    
    # Filtrage par nombre d'employés (post-requête)
    societes_list = []
    for s in societes:
        nb_employes = s["nb_employes"]
        if filtre_employes_min and nb_employes < int(filtre_employes_min):
            continue
        if filtre_employes_max and nb_employes > int(filtre_employes_max):
            continue
        societes_list.append(s)
    
    # Créer l'objet pagination
    from utils.pagination import Pagination
    pagination = Pagination(societes_list, page, per_page)
    pagination.total = total
    pagination.total_pages = math.ceil(total / per_page) if total > 0 else 1
    pagination.current_items = societes_list
    
    # Statistiques
    stats = {
        'total': db.execute("SELECT COUNT(*) AS n FROM societe").fetchone()["n"],
        'actives': db.execute("SELECT COUNT(*) AS n FROM societe WHERE actif = 1").fetchone()["n"],
        'inactives': db.execute("SELECT COUNT(*) AS n FROM societe WHERE actif = 0").fetchone()["n"],
    }
    
    return render_template(
        "societes/liste.html",
        societes=societes_list,
        pagination=pagination,
        stats=stats,
        filtre_recherche=filtre_recherche,
        filtre_statut=filtre_statut,
        filtre_employes_min=filtre_employes_min,
        filtre_employes_max=filtre_employes_max
    )


@societe_bp.route("/<int:id_societe>/toggle-actif", methods=["POST"])
@role_requis("super_admin")
def toggle_actif_societe(id_societe):
    db = get_db()
    societe = db.execute("SELECT * FROM societe WHERE id_societe = ?", (id_societe,)).fetchone()
    if societe is None:
        flash("Société introuvable.", "error")
        return redirect(url_for("societe.liste_societes"))

    nouveau_statut = 0 if societe["actif"] else 1
    
    # Compter les employés et utilisateurs avant la modification
    nb_employes = db.execute(
        "SELECT COUNT(*) AS n FROM employe WHERE id_societe = ?", (id_societe,)
    ).fetchone()["n"]
    
    nb_utilisateurs = db.execute(
        "SELECT COUNT(*) AS n FROM utilisateur WHERE id_societe = ?", (id_societe,)
    ).fetchone()["n"]
    
    if nouveau_statut == 0:
        # Désactiver la société
        db.execute("UPDATE societe SET actif = 0 WHERE id_societe = ?", (id_societe,))
        
        # Désactiver automatiquement TOUS les employés et utilisateurs de cette société
        db.execute("UPDATE employe SET actif = 0 WHERE id_societe = ?", (id_societe,))
        db.execute("UPDATE utilisateur SET actif = 0 WHERE id_societe = ?", (id_societe,))
        
        message = (
            f"Société désactivée. "
            f"{nb_employes} employé(s) et {nb_utilisateurs} utilisateur(s) ont été automatiquement désactivés."
        )
    else:
        # Réactiver la société
        db.execute("UPDATE societe SET actif = 1 WHERE id_societe = ?", (id_societe,))
        
        # Réactiver automatiquement TOUS les employés et utilisateurs de cette société
        db.execute("UPDATE employe SET actif = 1 WHERE id_societe = ?", (id_societe,))
        db.execute("UPDATE utilisateur SET actif = 1 WHERE id_societe = ?", (id_societe,))
        
        message = (
            f"Société réactivée. "
            f"{nb_employes} employé(s) et {nb_utilisateurs} utilisateur(s) ont été automatiquement réactivés."
        )
    
    db.commit()
    enregistrer_action(
        db, 
        "toggle_societe", 
        f"Société {societe['raison_sociale']} {'désactivée' if nouveau_statut == 0 else 'réactivée'} (id={id_societe})"
    )
    flash(message, "success")
    return redirect(url_for("societe.liste_societes"))


@societe_bp.route("/<int:id_societe>/supprimer", methods=["POST"])
@role_requis("super_admin")
def supprimer_societe(id_societe):
    db = get_db()
    societe = db.execute("SELECT * FROM societe WHERE id_societe = ?", (id_societe,)).fetchone()
    if societe is None:
        flash("Société introuvable.", "error")
        return redirect(url_for("societe.liste_societes"))

    # Suppression en cascade manuelle
    id_employes = [row["id_employe"] for row in db.execute(
        "SELECT id_employe FROM employe WHERE id_societe = ?", (id_societe,)
    ).fetchall()]

    for id_employe in id_employes:
        id_bulletins = [row["id_bulletin"] for row in db.execute(
            "SELECT id_bulletin FROM bulletin_paie WHERE id_employe = ?", (id_employe,)
        ).fetchall()]
        for id_bulletin in id_bulletins:
            db.execute("DELETE FROM ligne_bulletin WHERE id_bulletin = ?", (id_bulletin,))
        db.execute("DELETE FROM bulletin_paie WHERE id_employe = ?", (id_employe,))
        db.execute("DELETE FROM employe_element WHERE id_employe = ?", (id_employe,))

    db.execute("DELETE FROM employe WHERE id_societe = ?", (id_societe,))
    db.execute("DELETE FROM utilisateur WHERE id_societe = ?", (id_societe,))
    db.execute("""DELETE FROM palier_element WHERE id_element IN
                  (SELECT id_element FROM element_paie WHERE id_societe = ?)""", (id_societe,))
    db.execute("DELETE FROM element_paie WHERE id_societe = ?", (id_societe,))
    db.execute("DELETE FROM bareme_cotisation WHERE id_societe = ?", (id_societe,))
    db.execute("DELETE FROM tranche_ir WHERE id_societe = ?", (id_societe,))
    db.execute("DELETE FROM parametre_legal WHERE id_societe = ?", (id_societe,))
    db.execute("DELETE FROM societe WHERE id_societe = ?", (id_societe,))
    db.commit()

    enregistrer_action(db, "suppression_societe", f"Société {societe['raison_sociale']} supprimée définitivement (id={id_societe})")
    flash("Société et toutes ses données ont été supprimées définitivement.", "success")
    return redirect(url_for("societe.liste_societes"))


# routes/societe_routes.py - Ajouter la route d'upload

import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads/logos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Créer le dossier si nécessaire
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@societe_bp.route("/upload-logo", methods=["POST"])
@role_requis("super_admin")
def upload_logo():
    if 'logo' not in request.files:
        flash('Aucun fichier sélectionné.', 'error')
        return redirect(request.referrer)
    
    file = request.files['logo']
    if file.filename == '':
        flash('Aucun fichier sélectionné.', 'error')
        return redirect(request.referrer)
    
    if file and allowed_file(file.filename):
        # Sécuriser le nom du fichier
        filename = secure_filename(file.filename)
        # Ajouter un timestamp pour éviter les doublons
        import time
        filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Retourner le nom du fichier
        return {'success': True, 'filename': filename}
    else:
        return {'success': False, 'error': 'Format non accepté'}, 400