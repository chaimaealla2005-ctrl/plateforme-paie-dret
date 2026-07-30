# routes/personnel_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from db import get_db
from utils.decorators import role_requis
from utils.journal import enregistrer_action
from utils.pagination import Pagination
import math

personnel_bp = Blueprint("personnel", __name__, url_prefix="/personnel")

ROLES_DISPONIBLES = ["admin_societe", "rh", "comptable", "employe", "super_admin"]


@personnel_bp.route("/")
@role_requis("super_admin")
def liste_personnel():
    db = get_db()
    
    # Récupérer les paramètres de pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if per_page > 100:
        per_page = 100
    
    # Récupérer les paramètres de filtrage
    filtre_recherche = request.args.get('recherche', '').strip()
    filtre_role = request.args.get('role', 'tous')
    filtre_statut = request.args.get('statut', 'tous')
    filtre_societe = request.args.get('societe', 'tous')
    
    # Construction de la requête principale
    query = """
        SELECT 
            u.id_utilisateur,
            u.id_societe,
            u.nom,
            u.prenom,
            u.email,
            u.role,
            u.actif as utilisateur_actif,
            s.raison_sociale,
            e.id_employe,
            e.matricule,
            e.salaire_base,
            e.actif as employe_actif
        FROM utilisateur u
        LEFT JOIN societe s ON s.id_societe = u.id_societe
        LEFT JOIN employe e ON e.id_utilisateur = u.id_utilisateur
        WHERE 1=1
    """
    count_query = """
        SELECT COUNT(*) AS total
        FROM utilisateur u
        LEFT JOIN societe s ON s.id_societe = u.id_societe
        LEFT JOIN employe e ON e.id_utilisateur = u.id_utilisateur
        WHERE 1=1
    """
    params = []
    count_params = []
    
    # Filtre par recherche
    if filtre_recherche:
        query += " AND (u.nom LIKE ? OR u.prenom LIKE ? OR u.email LIKE ? OR e.matricule LIKE ?)"
        params.extend([f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%'])
        count_query += " AND (u.nom LIKE ? OR u.prenom LIKE ? OR u.email LIKE ? OR e.matricule LIKE ?)"
        count_params.extend([f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%'])
    
    # Filtre par rôle
    if filtre_role != 'tous' and filtre_role:
        query += " AND u.role = ?"
        params.append(filtre_role)
        count_query += " AND u.role = ?"
        count_params.append(filtre_role)
    
    # Filtre par statut
    if filtre_statut == 'actif':
        query += " AND u.actif = 1"
        count_query += " AND u.actif = 1"
    elif filtre_statut == 'inactif':
        query += " AND u.actif = 0"
        count_query += " AND u.actif = 0"
    
    # Filtre par société
    if filtre_societe != 'tous' and filtre_societe:
        query += " AND u.id_societe = ?"
        params.append(int(filtre_societe))
        count_query += " AND u.id_societe = ?"
        count_params.append(int(filtre_societe))
    
    # Obtenir le nombre total
    total = db.execute(count_query, count_params).fetchone()["total"]
    
    # Pagination
    offset = (page - 1) * per_page
    query += " ORDER BY u.role, u.nom LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    personnel = db.execute(query, params).fetchall()
    
    # Créer l'objet pagination
    pagination = Pagination([], page, per_page)
    pagination.total = total
    pagination.total_pages = math.ceil(total / per_page) if total > 0 else 1
    pagination.current_items = personnel
    pagination.start = offset
    
    # Récupérer les sociétés pour le filtre
    societes = db.execute("SELECT id_societe, raison_sociale FROM societe WHERE actif = 1 ORDER BY raison_sociale").fetchall()
    
    return render_template(
        "personnel/liste.html",
        personnel=personnel,
        pagination=pagination,
        societes=societes,
        filtre_recherche=filtre_recherche,
        filtre_role=filtre_role,
        filtre_statut=filtre_statut,
        filtre_societe=filtre_societe
    )


@personnel_bp.route("/nouveau", methods=["GET", "POST"])
@role_requis("super_admin")
def nouveau_personnel():
    db = get_db()
    societes = db.execute("SELECT * FROM societe WHERE actif = 1 ORDER BY raison_sociale").fetchall()

    if request.method == "POST":
        role = request.form["role"]
        id_societe = None if role == "super_admin" else (request.form.get("id_societe") or None)

        if role != "super_admin" and not id_societe:
            flash("Une société est obligatoire pour ce rôle.", "error")
            return redirect(url_for("personnel.nouveau_personnel"))

        # Créer l'utilisateur
        db.execute(
            """INSERT INTO utilisateur 
               (id_societe, nom, prenom, email, mot_de_passe_hash, role)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                id_societe,
                request.form["nom"],
                request.form["prenom"],
                request.form["email"].strip().lower(),
                generate_password_hash(request.form["mot_de_passe"]),
                role,
            ),
        )
        id_utilisateur = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # Si ce n'est pas un super_admin, créer aussi la fiche employé
        if role != "super_admin":
            db.execute(
                """INSERT INTO employe 
                   (id_societe, id_utilisateur, matricule, nom, prenom, email, telephone,
                    date_embauche, poste, grade, salaire_base, rib, nb_personnes_a_charge)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    id_societe,
                    id_utilisateur,
                    request.form["matricule"],
                    request.form["nom"],
                    request.form["prenom"],
                    request.form["email"].strip().lower(),
                    request.form.get("telephone", ""),
                    request.form["date_embauche"],
                    request.form.get("poste", role),
                    request.form.get("grade", ""),
                    request.form["salaire_base"],
                    request.form.get("rib", ""),
                    request.form.get("nb_personnes_a_charge", 0),
                ),
            )

        db.commit()
        enregistrer_action(db, "creation_personnel", f"Personnel créé : {request.form['email']} ({role})")
        flash("Personnel créé avec succès.", "success")
        return redirect(url_for("personnel.liste_personnel"))

    return render_template("personnel/formulaire.html", societes=societes, roles=ROLES_DISPONIBLES)


@personnel_bp.route("/<int:id_utilisateur>/modifier", methods=["GET", "POST"])
@role_requis("super_admin")
def modifier_personnel(id_utilisateur):
    db = get_db()
    utilisateur = db.execute("SELECT * FROM utilisateur WHERE id_utilisateur = ?", (id_utilisateur,)).fetchone()
    if utilisateur is None:
        flash("Personnel introuvable.", "error")
        return redirect(url_for("personnel.liste_personnel"))

    # Récupérer la fiche employé associée
    employe = db.execute("SELECT * FROM employe WHERE id_utilisateur = ?", (id_utilisateur,)).fetchone()

    societes = db.execute("SELECT * FROM societe WHERE actif = 1 ORDER BY raison_sociale").fetchall()

    if request.method == "POST":
        role = request.form["role"]
        id_societe = None if role == "super_admin" else (request.form.get("id_societe") or None)

        # Mettre à jour l'utilisateur
        db.execute(
            """UPDATE utilisateur
               SET nom = ?, prenom = ?, email = ?, role = ?, id_societe = ?
               WHERE id_utilisateur = ?""",
            (
                request.form["nom"],
                request.form["prenom"],
                request.form["email"].strip().lower(),
                role,
                id_societe,
                id_utilisateur,
            ),
        )

        # Si ce n'est pas un super_admin, mettre à jour ou créer la fiche employé
        if role != "super_admin":
            if employe:
                # Mettre à jour la fiche existante
                db.execute(
                    """UPDATE employe
                       SET id_societe = ?, matricule = ?, nom = ?, prenom = ?, email = ?,
                           telephone = ?, date_embauche = ?, poste = ?, grade = ?,
                           salaire_base = ?, rib = ?, nb_personnes_a_charge = ?
                       WHERE id_employe = ?""",
                    (
                        id_societe,
                        request.form["matricule"],
                        request.form["nom"],
                        request.form["prenom"],
                        request.form["email"].strip().lower(),
                        request.form.get("telephone", ""),
                        request.form["date_embauche"],
                        request.form.get("poste", role),
                        request.form.get("grade", ""),
                        request.form["salaire_base"],
                        request.form.get("rib", ""),
                        request.form.get("nb_personnes_a_charge", 0),
                        employe["id_employe"],
                    ),
                )
            else:
                # Créer la fiche employé si elle n'existe pas
                db.execute(
                    """INSERT INTO employe
                       (id_societe, id_utilisateur, matricule, nom, prenom, email,
                        telephone, date_embauche, poste, grade, salaire_base,
                        rib, nb_personnes_a_charge)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        id_societe,
                        id_utilisateur,
                        request.form["matricule"],
                        request.form["nom"],
                        request.form["prenom"],
                        request.form["email"].strip().lower(),
                        request.form.get("telephone", ""),
                        request.form["date_embauche"],
                        request.form.get("poste", role),
                        request.form.get("grade", ""),
                        request.form["salaire_base"],
                        request.form.get("rib", ""),
                        request.form.get("nb_personnes_a_charge", 0),
                    ),
                )

        db.commit()
        enregistrer_action(db, "modification_personnel", f"Personnel modifié (id={id_utilisateur}) -> rôle {role}")
        flash("Personnel mis à jour avec succès.", "success")
        return redirect(url_for("personnel.liste_personnel"))

    return render_template("personnel/formulaire.html", personnel=utilisateur, employe=employe, societes=societes, roles=ROLES_DISPONIBLES)


@personnel_bp.route("/<int:id_utilisateur>/toggle-actif", methods=["POST"])
@role_requis("super_admin")
def toggle_actif_personnel(id_utilisateur):
    db = get_db()
    utilisateur = db.execute("SELECT * FROM utilisateur WHERE id_utilisateur = ?", (id_utilisateur,)).fetchone()
    if utilisateur is None:
        flash("Personnel introuvable.", "error")
        return redirect(url_for("personnel.liste_personnel"))

    # Ne pas désactiver son propre compte
    if id_utilisateur == session.get("id_utilisateur"):
        flash("Vous ne pouvez pas désactiver votre propre compte.", "error")
        return redirect(url_for("personnel.liste_personnel"))

    nouveau_statut = 0 if utilisateur["actif"] else 1
    db.execute("UPDATE utilisateur SET actif = ? WHERE id_utilisateur = ?", (nouveau_statut, id_utilisateur))
    
    # Désactiver/réactiver aussi la fiche employé associée
    db.execute("UPDATE employe SET actif = ? WHERE id_utilisateur = ?", (nouveau_statut, id_utilisateur))
    
    db.commit()
    action = "réactivé" if nouveau_statut else "désactivé"
    enregistrer_action(db, "toggle_personnel", f"Personnel {utilisateur['email']} {action}")
    flash(f"Personnel {action}.", "success")
    return redirect(url_for("personnel.liste_personnel"))


@personnel_bp.route("/<int:id_utilisateur>/supprimer", methods=["POST"])
@role_requis("super_admin")
def supprimer_personnel(id_utilisateur):
    db = get_db()
    utilisateur = db.execute("SELECT * FROM utilisateur WHERE id_utilisateur = ?", (id_utilisateur,)).fetchone()
    if utilisateur is None:
        flash("Personnel introuvable.", "error")
        return redirect(url_for("personnel.liste_personnel"))

    if id_utilisateur == session.get("id_utilisateur"):
        flash("Vous ne pouvez pas supprimer votre propre compte.", "error")
        return redirect(url_for("personnel.liste_personnel"))

    if utilisateur["role"] == "super_admin":
        nb_super_admins = db.execute(
            "SELECT COUNT(*) AS n FROM utilisateur WHERE role = 'super_admin'"
        ).fetchone()["n"]
        if nb_super_admins <= 1:
            flash("Impossible de supprimer le dernier super-admin.", "error")
            return redirect(url_for("personnel.liste_personnel"))

    # Supprimer la fiche employé et ses bulletins
    employe = db.execute("SELECT * FROM employe WHERE id_utilisateur = ?", (id_utilisateur,)).fetchone()
    if employe:
        id_employe = employe["id_employe"]
        # Supprimer les lignes et bulletins
        id_bulletins = [r["id_bulletin"] for r in db.execute(
            "SELECT id_bulletin FROM bulletin_paie WHERE id_employe = ?", (id_employe,)
        ).fetchall()]
        for id_bulletin in id_bulletins:
            db.execute("DELETE FROM ligne_bulletin WHERE id_bulletin = ?", (id_bulletin,))
        db.execute("DELETE FROM bulletin_paie WHERE id_employe = ?", (id_employe,))
        db.execute("DELETE FROM employe_element WHERE id_employe = ?", (id_employe,))
        db.execute("DELETE FROM employe WHERE id_employe = ?", (id_employe,))

    # Supprimer l'utilisateur
    db.execute("UPDATE journal_action SET id_utilisateur = NULL WHERE id_utilisateur = ?", (id_utilisateur,))
    db.execute("DELETE FROM utilisateur WHERE id_utilisateur = ?", (id_utilisateur,))
    db.commit()

    enregistrer_action(db, "suppression_personnel", f"Personnel {utilisateur['email']} supprimé définitivement")
    flash("Personnel supprimé définitivement.", "success")
    return redirect(url_for("personnel.liste_personnel"))