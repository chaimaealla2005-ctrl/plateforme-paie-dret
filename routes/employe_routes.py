from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash
from db import get_db
from utils.decorators import role_requis, societe_requise
from utils.journal import enregistrer_action
from utils.pagination import Pagination
import math
from utils.export import export_employes, export_to_csv, export_to_excel

employe_bp = Blueprint("employe", __name__, url_prefix="/employes")


# routes/employe_routes.py (ajouter les paramètres de filtrage)

@employe_bp.route("/")
@role_requis("rh", "admin_societe", "comptable", "super_admin")
@societe_requise
def liste_employes():
    db = get_db()
    
    # Récupérer les paramètres de pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if per_page > 100:
        per_page = 100
    
    # Récupérer les paramètres de filtrage
    filtre_recherche = request.args.get('recherche', '').strip()
    filtre_statut = request.args.get('statut', 'tous')
    filtre_poste = request.args.get('poste', 'tous')
    
    if session["role"] == "super_admin":
        query = """SELECT e.*, s.raison_sociale FROM employe e
                   JOIN societe s ON s.id_societe = e.id_societe
                   WHERE 1=1"""
        params = []
        count_query = "SELECT COUNT(*) AS total FROM employe e JOIN societe s ON s.id_societe = e.id_societe WHERE 1=1"
        count_params = []
    else:
        query = "SELECT * FROM employe WHERE id_societe = ?"
        params = [session["id_societe"]]
        count_query = "SELECT COUNT(*) AS total FROM employe WHERE id_societe = ?"
        count_params = [session["id_societe"]]
    
    # Filtre par recherche
    if filtre_recherche:
        if session["role"] == "super_admin":
            query += " AND (e.nom LIKE ? OR e.prenom LIKE ? OR e.matricule LIKE ?)"
            params.extend([f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%'])
            count_query += " AND (e.nom LIKE ? OR e.prenom LIKE ? OR e.matricule LIKE ?)"
            count_params.extend([f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%'])
        else:
            query += " AND (nom LIKE ? OR prenom LIKE ? OR matricule LIKE ?)"
            params.extend([f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%'])
            count_query += " AND (nom LIKE ? OR prenom LIKE ? OR matricule LIKE ?)"
            count_params.extend([f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%'])
    
    # Filtre par statut
    if filtre_statut == 'actif':
        query += " AND actif = 1"
        count_query += " AND actif = 1"
    elif filtre_statut == 'inactif':
        query += " AND actif = 0"
        count_query += " AND actif = 0"
    
    # Filtre par poste
    if filtre_poste != 'tous' and filtre_poste:
        if session["role"] == "super_admin":
            query += " AND e.poste = ?"
        else:
            query += " AND poste = ?"
        params.append(filtre_poste)
        count_query += " AND poste = ?"
        count_params.append(filtre_poste)
    
    # Obtenir le nombre total d'enregistrements
    total = db.execute(count_query, count_params).fetchone()["total"]
    
    # Pagination
    offset = (page - 1) * per_page
    if session["role"] == "super_admin":
        query += " ORDER BY s.raison_sociale, e.nom LIMIT ? OFFSET ?"
    else:
        query += " ORDER BY nom LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    employes = db.execute(query, params).fetchall()
    
    # Créer l'objet pagination
    pagination = Pagination(employes, page, per_page)
    pagination.total = total
    pagination.total_pages = math.ceil(total / per_page) if total > 0 else 1
    pagination.current_items = employes
    
    # Récupérer la liste des postes pour le filtre
    if session["role"] == "super_admin":
        postes = db.execute("SELECT DISTINCT poste FROM employe WHERE poste IS NOT NULL AND poste != '' ORDER BY poste").fetchall()
    else:
        postes = db.execute(
            "SELECT DISTINCT poste FROM employe WHERE id_societe = ? AND poste IS NOT NULL AND poste != '' ORDER BY poste",
            (session["id_societe"],)
        ).fetchall()
    
    # Statistiques
    if session["role"] == "super_admin":
        total_actifs = db.execute("SELECT COUNT(*) AS n FROM employe WHERE actif = 1").fetchone()["n"]
        total_inactifs = db.execute("SELECT COUNT(*) AS n FROM employe WHERE actif = 0").fetchone()["n"]
    else:
        total_actifs = db.execute(
            "SELECT COUNT(*) AS n FROM employe WHERE id_societe = ? AND actif = 1",
            (session["id_societe"],)
        ).fetchone()["n"]
        total_inactifs = db.execute(
            "SELECT COUNT(*) AS n FROM employe WHERE id_societe = ? AND actif = 0",
            (session["id_societe"],)
        ).fetchone()["n"]
    
    return render_template(
        "employes/liste.html",
        employes=employes,
        pagination=pagination,
        postes=postes,
        filtre_recherche=filtre_recherche,
        filtre_statut=filtre_statut,
        filtre_poste=filtre_poste,
        total_actifs=total_actifs,
        total_inactifs=total_inactifs,
        total_employes=total
    )


# routes/employe_routes.py - Fonction nouvel_employe MODIFIEE

@employe_bp.route("/nouveau", methods=["GET", "POST"])
@role_requis("rh", "admin_societe", "super_admin")
@societe_requise
def nouvel_employe():
    db = get_db()
    societes = None
    if session["role"] == "super_admin":
        societes = db.execute("SELECT * FROM societe WHERE actif = 1 ORDER BY raison_sociale").fetchall()
    
    # Déterminer les rôles disponibles pour l'Admin Société
    roles_disponibles = ["employe"]
    if session["role"] in ["admin_societe", "super_admin"]:
        roles_disponibles = ["employe", "rh", "comptable"]
    if session["role"] == "super_admin":
        roles_disponibles = ["employe", "rh", "comptable", "admin_societe", "super_admin"]
    
    if request.method == "POST":
        id_societe = request.form["id_societe"] if session["role"] == "super_admin" else session["id_societe"]
        
        # Récupérer le rôle choisi
        role = request.form.get("role", "employe")
        
        # Vérifier que l'Admin Société ne peut pas créer de Super Admin
        if role == "super_admin" and session["role"] != "super_admin":
            flash("Vous ne pouvez pas créer un Super Admin.", "error")
            return redirect(url_for("employe.nouvel_employe"))
        
        # Vérifier le matricule unique
        matricule = request.form.get("matricule", "").strip()
        if not matricule:
            flash("Le matricule est obligatoire.", "error")
            return redirect(url_for("employe.nouvel_employe"))
        
        existant = db.execute(
            "SELECT * FROM employe WHERE id_societe = ? AND matricule = ?",
            (id_societe, matricule)
        ).fetchone()
        if existant:
            flash(f"Le matricule '{matricule}' existe déjà.", "error")
            return redirect(url_for("employe.nouvel_employe"))
        
        # Créer l'utilisateur (si mot de passe fourni ou si rôle différent d'employé)
        mot_de_passe = request.form.get("mot_de_passe", "").strip()
        id_utilisateur = None
        
        # Si rôle différent d'employé, mot de passe obligatoire
        if role != "employe" and not mot_de_passe:
            flash(f"Un mot de passe est obligatoire pour le rôle '{role}'.", "error")
            return redirect(url_for("employe.nouvel_employe"))
        
        if role != "employe" or mot_de_passe:
            # Vérifier que l'email n'existe pas déjà
            email = request.form.get("email", "").strip().lower()
            if not email:
                flash("L'email est obligatoire pour créer un compte utilisateur.", "error")
                return redirect(url_for("employe.nouvel_employe"))
            
            existant_user = db.execute(
                "SELECT * FROM utilisateur WHERE email = ?",
                (email,)
            ).fetchone()
            if existant_user:
                flash(f"L'email '{email}' est déjà utilisé.", "error")
                return redirect(url_for("employe.nouvel_employe"))
            
            db.execute(
                """INSERT INTO utilisateur (id_societe, nom, prenom, email, mot_de_passe_hash, role, actif)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (
                    id_societe,
                    request.form["nom"],
                    request.form["prenom"],
                    email,
                    generate_password_hash(mot_de_passe) if mot_de_passe else None,
                    role,
                ),
            )
            id_utilisateur = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        
        # Créer l'employé
        db.execute(
            """INSERT INTO employe 
               (id_societe, id_utilisateur, matricule, nom, prenom, cin, email, telephone,
                date_embauche, poste, grade, salaire_base, rib, 
                cnss_numero, situation_familiale, nb_personnes_a_charge, 
                jours_travailles, heures_sup, actif)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                id_societe,
                id_utilisateur,
                matricule,
                request.form["nom"],
                request.form["prenom"],
                request.form.get("cin", ""),
                request.form.get("email", ""),
                request.form.get("telephone", ""),
                request.form["date_embauche"],
                request.form.get("poste", role if role != "employe" else ""),
                request.form.get("grade", ""),
                request.form["salaire_base"],
                request.form.get("rib", ""),
                request.form.get("cnss_numero", ""),
                request.form.get("situation_familiale", "MARIE"),
                int(request.form.get("nb_personnes_a_charge", 0)),
                int(request.form.get("jours_travailles", 26)),
                float(request.form.get("heures_sup", 0)),
            ),
        )
        
        # Récupérer l'ID du nouvel employé
        id_employe = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        
        # ============================================================
        # AFFECTATION AUTOMATIQUE DE LA PRIME D'ANCIENNETE
        # ============================================================
        prime = db.execute(
            "SELECT id_element FROM element_paie WHERE code = ?",
            ('PRIME_ANCIENNETE',)
        ).fetchone()
        if prime:
            db.execute(
                "INSERT INTO employe_element (id_employe, id_element, date_debut) VALUES (?, ?, date('now'))",
                (id_employe, prime[0])
            )
        
        db.commit()
        
        message = f"Employé créé avec succès."
        if id_utilisateur:
            message += f" Compte utilisateur (rôle: {role}) créé."
        flash(message, "success")
        return redirect(url_for("employe.liste_employes"))

    return render_template(
        "employes/formulaire.html",
        societes=societes,
        employe=None,
        roles_disponibles=roles_disponibles,
        role_actuel=session["role"]
    )


# routes/employe_routes.py - Modifier les décorateurs pour inclure 'comptable'

# ============================================================
# MODIFIER UN EMPLOYE - Ajouter comptable
# ============================================================
# routes/employe_routes.py - Modifier les décorateurs

# ============================================================
# MODIFIER UN EMPLOYE
# ============================================================
@employe_bp.route("/<int:id_employe>/modifier", methods=["GET", "POST"])
@role_requis("rh", "admin_societe", "comptable", "super_admin")  # ← Ajouter 'comptable' et 'super_admin'
@societe_requise
def modifier_employe(id_employe):
    db = get_db()
    
    # Vérifier que l'employé appartient à la société de l'utilisateur
    if session["role"] not in ["super_admin"]:
        employe = db.execute(
            "SELECT * FROM employe WHERE id_employe = ? AND id_societe = ?",
            (id_employe, session["id_societe"])
        ).fetchone()
    else:
        employe = db.execute(
            "SELECT * FROM employe WHERE id_employe = ?",
            (id_employe,)
        ).fetchone()
    
    if employe is None:
        flash("Employé introuvable.", "error")
        return redirect(url_for("employe.liste_employes"))
    
    # Récupérer les sociétés pour le super_admin
    societes = None
    if session["role"] == "super_admin":
        societes = db.execute("SELECT * FROM societe WHERE actif = 1 ORDER BY raison_sociale").fetchall()
    
    if request.method == "POST":
        # Récupérer les données du formulaire
        id_societe = request.form["id_societe"] if session["role"] == "super_admin" else employe["id_societe"]
        
        # Restrictions pour le comptable (ne peut pas modifier le salaire de base, RIB, etc.)
        if session["role"] == "comptable":
            # Le comptable ne peut pas modifier ces champs
            salaire_base = employe["salaire_base"]
            rib = employe["rib"]
            nb_personnes_a_charge = employe["nb_personnes_a_charge"] if employe["nb_personnes_a_charge"] else 0
            situation_familiale = employe["situation_familiale"] if employe["situation_familiale"] else "MARIE"
            cnss_numero = employe["cnss_numero"] if employe["cnss_numero"] else ""
        else:
            salaire_base = request.form["salaire_base"]
            rib = request.form.get("rib", "")
            nb_personnes_a_charge = int(request.form.get("nb_personnes_a_charge", 0))
            situation_familiale = request.form.get("situation_familiale", "MARIE")
            cnss_numero = request.form.get("cnss_numero", "")
        
        db.execute(
            """UPDATE employe
               SET id_societe = ?, matricule = ?, nom = ?, prenom = ?, cin = ?, email = ?,
                   telephone = ?, date_embauche = ?, poste = ?, grade = ?, salaire_base = ?,
                   rib = ?, nb_personnes_a_charge = ?, situation_familiale = ?, cnss_numero = ?,
                   jours_travailles = ?, heures_sup = ?
               WHERE id_employe = ?""",
            (
                id_societe,
                request.form["matricule"],
                request.form["nom"],
                request.form["prenom"],
                request.form.get("cin", ""),
                request.form.get("email", ""),
                request.form.get("telephone", ""),
                request.form["date_embauche"],
                request.form.get("poste", ""),
                request.form.get("grade", ""),
                float(salaire_base),
                rib,
                nb_personnes_a_charge,
                situation_familiale,
                cnss_numero,
                int(request.form.get("jours_travailles", 26)),
                float(request.form.get("heures_sup", 0)),
                id_employe,
            ),
        )
        db.commit()
        enregistrer_action(db, "modification_employe", f"Employé modifié : {request.form['nom']} {request.form['prenom']}")
        flash("Employé mis à jour avec succès.", "success")
        return redirect(url_for("employe.liste_employes"))

    return render_template("employes/formulaire.html", societes=societes, employe=employe, role=session["role"])


@employe_bp.route("/<int:id_employe>/toggle-actif", methods=["POST"])
@role_requis("rh", "admin_societe", "super_admin")
def toggle_actif_employe(id_employe):
    db = get_db()
    employe = db.execute("SELECT * FROM employe WHERE id_employe = ?", (id_employe,)).fetchone()
    if employe is None:
        flash("Employé introuvable.", "error")
        return redirect(url_for("employe.liste_employes"))

    if session["role"] != "super_admin" and employe["id_societe"] != session["id_societe"]:
        abort(403)

    nouveau_statut = 0 if employe["actif"] else 1
    db.execute("UPDATE employe SET actif = ? WHERE id_employe = ?", (nouveau_statut, id_employe))
    db.commit()
    action = "réactivé" if nouveau_statut else "désactivé"
    enregistrer_action(db, "toggle_employe", f"Employé {employe['nom']} {employe['prenom']} {action}")
    flash(f"Employé {action}.", "success")
    return redirect(url_for("employe.liste_employes"))


@employe_bp.route("/<int:id_employe>/supprimer", methods=["POST"])
@role_requis("admin_societe", "super_admin")
def supprimer_employe(id_employe):
    db = get_db()
    employe = db.execute("SELECT * FROM employe WHERE id_employe = ?", (id_employe,)).fetchone()
    if employe is None:
        flash("Employé introuvable.", "error")
        return redirect(url_for("employe.liste_employes"))

    if session["role"] != "super_admin" and employe["id_societe"] != session["id_societe"]:
        abort(403)

    if employe["id_utilisateur"]:
        flash(
            "Impossible de supprimer cet employé : il a aussi un compte de connexion. "
            "Supprimez d'abord son compte depuis l'onglet Utilisateurs.",
            "error",
        )
        return redirect(url_for("employe.liste_employes"))

    id_bulletins = [r["id_bulletin"] for r in db.execute(
        "SELECT id_bulletin FROM bulletin_paie WHERE id_employe = ?", (id_employe,)
    ).fetchall()]
    for id_bulletin in id_bulletins:
        db.execute("DELETE FROM ligne_bulletin WHERE id_bulletin = ?", (id_bulletin,))
    db.execute("DELETE FROM bulletin_paie WHERE id_employe = ?", (id_employe,))
    db.execute("DELETE FROM employe_element WHERE id_employe = ?", (id_employe,))
    db.execute("DELETE FROM employe WHERE id_employe = ?", (id_employe,))
    db.commit()

    enregistrer_action(db, "suppression_employe", f"Employé {employe['nom']} {employe['prenom']} supprimé définitivement")
    flash("Employé supprimé définitivement.", "success")
    return redirect(url_for("employe.liste_employes"))

# ============================================================
# PROFIL DE L'EMPLOYE
# ============================================================
# routes/employe_routes.py

@employe_bp.route("/profil")
@role_requis("employe", "rh", "comptable", "admin_societe", "super_admin")
def profil():
    db = get_db()
    
    employe = db.execute(
        """SELECT e.*, s.raison_sociale 
           FROM employe e
           JOIN societe s ON s.id_societe = e.id_societe
           WHERE e.id_utilisateur = ?""",
        (session["id_utilisateur"],)
    ).fetchone()
    
    if employe is None:
        utilisateur = db.execute(
            "SELECT * FROM utilisateur WHERE id_utilisateur = ?",
            (session["id_utilisateur"],)
        ).fetchone()
        
        if utilisateur:
            db.execute(
                """INSERT INTO employe 
                   (id_societe, id_utilisateur, matricule, nom, prenom, email, date_embauche, poste, salaire_base, actif)
                   VALUES (?, ?, ?, ?, ?, ?, date('now'), ?, 0, 1)""",
                (
                    utilisateur["id_societe"],
                    utilisateur["id_utilisateur"],
                    f"EMP-{utilisateur['id_utilisateur']}",
                    utilisateur["nom"],
                    utilisateur["prenom"],
                    utilisateur["email"],
                    utilisateur["role"]
                )
            )
            db.commit()
            employe = db.execute(
                "SELECT * FROM employe WHERE id_utilisateur = ?",
                (session["id_utilisateur"],)
            ).fetchone()
    
    if employe is None:
        flash("Profil employé introuvable.", "error")
        return redirect(url_for("index"))
    
    return render_template("employes/profil.html", employe=employe)


# ============================================================
# MODIFICATION DU PROFIL (EMAIL ET TELEPHONE UNIQUEMENT)
# ============================================================
@employe_bp.route("/profil/modifier", methods=["GET", "POST"])
@role_requis("employe", "rh", "comptable", "admin_societe", "super_admin")
def modifier_profil():
    """Modifier certaines informations personnelles (email, téléphone)"""
    db = get_db()
    
    # Récupérer l'employé connecté
    employe = db.execute(
        """SELECT e.* FROM employe e
           WHERE e.id_utilisateur = ?""",
        (session["id_utilisateur"],)
    ).fetchone()
    
    if employe is None:
        flash("Profil employé introuvable.", "error")
        return redirect(url_for("index"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        telephone = request.form.get("telephone", "").strip()
        
        # Vérifier que l'email n'est pas déjà utilisé par un autre utilisateur
        if email:
            existant = db.execute(
                "SELECT * FROM utilisateur WHERE email = ? AND id_utilisateur != ?",
                (email, session["id_utilisateur"])
            ).fetchone()
            if existant:
                flash("Cet email est déjà utilisé par un autre compte.", "error")
                return render_template("employes/modifier_profil.html", employe=employe)
        
        # Mettre à jour l'email dans la table utilisateur
        db.execute(
            "UPDATE utilisateur SET email = ? WHERE id_utilisateur = ?",
            (email, session["id_utilisateur"])
        )
        
        # Mettre à jour l'email et le téléphone dans la table employe
        db.execute(
            "UPDATE employe SET email = ?, telephone = ? WHERE id_employe = ?",
            (email, telephone, employe["id_employe"])
        )
        db.commit()
        
        # Mettre à jour la session
        session["email"] = email
        
        enregistrer_action(db, "modification_profil", f"Employé {employe['nom']} a modifié son profil")
        flash("Profil mis à jour avec succès.", "success")
        return redirect(url_for("employe.profil"))
    
    return render_template("employes/modifier_profil.html", employe=employe)

# routes/employe_routes.py - Ajouter

@employe_bp.route("/statistiques-rh")
@role_requis("rh")
@societe_requise
def statistiques_rh():
    db = get_db()
    id_societe = session.get("id_societe")
    
    # Statistiques employés
    total_employes = db.execute(
        "SELECT COUNT(*) AS n FROM employe WHERE id_societe = ? AND actif = 1",
        (id_societe,)
    ).fetchone()["n"]
    
    total_inactifs = db.execute(
        "SELECT COUNT(*) AS n FROM employe WHERE id_societe = ? AND actif = 0",
        (id_societe,)
    ).fetchone()["n"]
    
    # Répartition par poste
    postes = db.execute(
        """SELECT poste, COUNT(*) AS n FROM employe 
           WHERE id_societe = ? AND actif = 1 AND poste IS NOT NULL AND poste != ''
           GROUP BY poste ORDER BY n DESC""",
        (id_societe,)
    ).fetchall()
    
    # Ancienneté moyenne
    anciennete_moyenne = db.execute(
        """SELECT AVG(
            CAST(strftime('%Y', 'now') - strftime('%Y', date_embauche) AS REAL)
        ) AS moyenne FROM employe WHERE id_societe = ? AND actif = 1 AND date_embauche IS NOT NULL""",
        (id_societe,)
    ).fetchone()["moyenne"]
    
    # Derniers employés embauchés
    derniers_embauches = db.execute(
        """SELECT * FROM employe 
           WHERE id_societe = ? AND actif = 1
           ORDER BY date_embauche DESC
           LIMIT 5""",
        (id_societe,)
    ).fetchall()
    
    return render_template(
        "rh/statistiques.html",
        total_employes=total_employes,
        total_inactifs=total_inactifs,
        postes=postes,
        anciennete_moyenne=round(anciennete_moyenne or 0, 1),
        derniers_embauches=derniers_embauches
    )

@employe_bp.route("/export")
@role_requis("rh", "admin_societe", "comptable", "super_admin")
@societe_requise
def export_employes_csv():
    """Exporter la liste des employés en CSV/Excel"""
    db = get_db()
    
    # Récupérer les employés (avec les filtres actuels)
    if session["role"] == "super_admin":
        employes = db.execute(
            """SELECT e.*, s.raison_sociale FROM employe e
               JOIN societe s ON s.id_societe = e.id_societe
               ORDER BY s.raison_sociale, e.nom"""
        ).fetchall()
    else:
        employes = db.execute(
            "SELECT * FROM employe WHERE id_societe = ? ORDER BY nom",
            (session["id_societe"],)
        ).fetchall()
    
    # Préparer les données
    headers, data = export_employes(employes)
    
    # Choisir le format (par défaut CSV)
    format_type = request.args.get('format', 'csv')
    
    if format_type == 'excel':
        return export_to_excel(data, headers, 'employes')
    else:
        return export_to_csv(data, headers, 'employes')



# routes/employe_routes.py - Ajouter une route de correction

@employe_bp.route("/fix-anciennete")
@role_requis("super_admin")
def fix_anciennete():
    """Corriger la prime d'ancienneté pour tous les employés qui n'en ont pas"""
    db = get_db()
    
    # Récupérer l'ID de l'élément PRIME_ANCIENNETE
    prime = db.execute(
        "SELECT id_element FROM element_paie WHERE code = ?",
        ('PRIME_ANCIENNETE',)
    ).fetchone()
    
    if not prime:
        flash("❌ Élément PRIME_ANCIENNETE non trouvé dans le catalogue.", "error")
        return redirect(url_for("employe.liste_employes"))
    
    id_element = prime[0]
    
    # Récupérer tous les employés qui n'ont pas la prime
    employes = db.execute(
        """SELECT id_employe FROM employe 
           WHERE id_employe NOT IN (
               SELECT id_employe FROM employe_element WHERE id_element = ?
           )""",
        (id_element,)
    ).fetchall()
    
    count = 0
    for e in employes:
        db.execute(
            "INSERT INTO employe_element (id_employe, id_element, date_debut) VALUES (?, ?, date('now'))",
            (e[0], id_element)
        )
        count += 1
    
    db.commit()
    flash(f"✅ Prime d'ancienneté affectée à {count} employé(s).", "success")
    return redirect(url_for("employe.liste_employes"))