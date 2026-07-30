from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from db import get_db
from utils.decorators import role_requis
from utils.journal import enregistrer_action

utilisateur_bp = Blueprint("utilisateur", __name__, url_prefix="/utilisateurs")

ROLES_DISPONIBLES = ["super_admin", "admin_societe", "rh", "comptable", "employe"]


@utilisateur_bp.route("/")
@role_requis("super_admin")
def liste_utilisateurs():
    db = get_db()
    utilisateurs = db.execute(
        """SELECT u.*, s.raison_sociale
           FROM utilisateur u
           LEFT JOIN societe s ON s.id_societe = u.id_societe
           ORDER BY u.role, u.nom"""
    ).fetchall()
    return render_template("utilisateurs/liste.html", utilisateurs=utilisateurs)


@utilisateur_bp.route("/nouveau", methods=["GET", "POST"])
@role_requis("super_admin")
def nouvel_utilisateur():
    db = get_db()
    societes = db.execute("SELECT * FROM societe WHERE actif = 1 ORDER BY raison_sociale").fetchall()

    if request.method == "POST":
        role = request.form["role"]
        # Un super_admin n'est rattache a aucune societe
        id_societe = None if role == "super_admin" else (request.form.get("id_societe") or None)

        if role != "super_admin" and not id_societe:
            flash("Une société est obligatoire pour ce rôle.", "error")
            return redirect(url_for("utilisateur.nouvel_utilisateur"))

        db.execute(
            """INSERT INTO utilisateur (id_societe, nom, prenom, email, mot_de_passe_hash, role)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                id_societe, request.form["nom"], request.form["prenom"],
                request.form["email"].strip().lower(),
                generate_password_hash(request.form["mot_de_passe"]),
                role,
            ),
        )
        id_utilisateur = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # IMPORTANT : quel que soit son role (sauf super_admin), une personne qui
        # travaille pour une societe est AUSSI un employe (fiche RH/paie), en plus
        # d'avoir un compte de connexion avec des droits specifiques.
        if role != "super_admin":
            db.execute(
                """INSERT INTO employe (id_societe, id_utilisateur, matricule, nom, prenom,
                                         email, telephone, date_embauche, poste, salaire_base,
                                         nb_personnes_a_charge)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    id_societe, id_utilisateur, request.form["matricule"],
                    request.form["nom"], request.form["prenom"],
                    request.form["email"].strip().lower(), request.form.get("telephone", ""),
                    request.form["date_embauche"], request.form.get("poste", role),
                    request.form["salaire_base"], request.form.get("nb_personnes_a_charge", 0),
                ),
            )

        db.commit()
        enregistrer_action(db, "creation_utilisateur", f"Utilisateur créé : {request.form['email']} ({role})")
        flash("Utilisateur créé avec succès (avec sa fiche employé).", "success")
        return redirect(url_for("utilisateur.liste_utilisateurs"))

    return render_template("utilisateurs/formulaire.html", utilisateur=None, societes=societes, roles=ROLES_DISPONIBLES)


@utilisateur_bp.route("/<int:id_utilisateur>/modifier", methods=["GET", "POST"])
@role_requis("super_admin")
def modifier_utilisateur(id_utilisateur):
    db = get_db()
    utilisateur = db.execute("SELECT * FROM utilisateur WHERE id_utilisateur = ?", (id_utilisateur,)).fetchone()
    if utilisateur is None:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("utilisateur.liste_utilisateurs"))

    societes = db.execute("SELECT * FROM societe WHERE actif = 1 ORDER BY raison_sociale").fetchall()

    if request.method == "POST":
        role = request.form["role"]
        id_societe = None if role == "super_admin" else (request.form.get("id_societe") or None)

        db.execute(
            """UPDATE utilisateur
               SET nom = ?, prenom = ?, email = ?, role = ?, id_societe = ?
               WHERE id_utilisateur = ?""",
            (request.form["nom"], request.form["prenom"], request.form["email"].strip().lower(),
             role, id_societe, id_utilisateur),
        )
        db.commit()
        enregistrer_action(db, "modification_utilisateur", f"Utilisateur modifié (id={id_utilisateur}) -> rôle {role}")
        flash("Utilisateur mis à jour.", "success")
        return redirect(url_for("utilisateur.liste_utilisateurs"))

    return render_template("utilisateurs/formulaire.html", utilisateur=utilisateur, societes=societes, roles=ROLES_DISPONIBLES)


@utilisateur_bp.route("/<int:id_utilisateur>/toggle-actif", methods=["POST"])
@role_requis("super_admin")
def toggle_actif_utilisateur(id_utilisateur):
    db = get_db()
    utilisateur = db.execute("SELECT * FROM utilisateur WHERE id_utilisateur = ?", (id_utilisateur,)).fetchone()
    if utilisateur is None:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("utilisateur.liste_utilisateurs"))

    nouveau_statut = 0 if utilisateur["actif"] else 1
    db.execute("UPDATE utilisateur SET actif = ? WHERE id_utilisateur = ?", (nouveau_statut, id_utilisateur))
    db.commit()
    action = "réactivé" if nouveau_statut else "désactivé"
    enregistrer_action(db, "toggle_utilisateur", f"Utilisateur {utilisateur['email']} {action}")
    flash(f"Utilisateur {action}.", "success")
    return redirect(url_for("utilisateur.liste_utilisateurs"))


@utilisateur_bp.route("/<int:id_utilisateur>/supprimer", methods=["POST"])
@role_requis("super_admin")
def supprimer_utilisateur(id_utilisateur):
    db = get_db()
    utilisateur = db.execute("SELECT * FROM utilisateur WHERE id_utilisateur = ?", (id_utilisateur,)).fetchone()
    if utilisateur is None:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("utilisateur.liste_utilisateurs"))

    if id_utilisateur == session.get("id_utilisateur"):
        flash("Vous ne pouvez pas supprimer votre propre compte pendant que vous êtes connecté.", "error")
        return redirect(url_for("utilisateur.liste_utilisateurs"))

    if utilisateur["role"] == "super_admin":
        nb_super_admins = db.execute(
            "SELECT COUNT(*) AS n FROM utilisateur WHERE role = 'super_admin'"
        ).fetchone()["n"]
        if nb_super_admins <= 1:
            flash("Impossible de supprimer le dernier super-admin de la plateforme.", "error")
            return redirect(url_for("utilisateur.liste_utilisateurs"))

    # Si cet utilisateur a aussi une fiche employe (cas normal pour admin_societe/rh/comptable/employe),
    # on supprime son historique de paie en cascade avant de supprimer la fiche elle-meme.
    employe = db.execute("SELECT * FROM employe WHERE id_utilisateur = ?", (id_utilisateur,)).fetchone()
    if employe:
        id_employe = employe["id_employe"]
        id_bulletins = [r["id_bulletin"] for r in db.execute(
            "SELECT id_bulletin FROM bulletin_paie WHERE id_employe = ?", (id_employe,)
        ).fetchall()]
        for id_bulletin in id_bulletins:
            db.execute("DELETE FROM ligne_bulletin WHERE id_bulletin = ?", (id_bulletin,))
        db.execute("DELETE FROM bulletin_paie WHERE id_employe = ?", (id_employe,))
        db.execute("DELETE FROM employe_element WHERE id_employe = ?", (id_employe,))
        db.execute("DELETE FROM employe WHERE id_employe = ?", (id_employe,))

    # On detache le journal (au lieu de le supprimer) pour garder une trace d'audit
    db.execute("UPDATE journal_action SET id_utilisateur = NULL WHERE id_utilisateur = ?", (id_utilisateur,))
    db.execute("DELETE FROM utilisateur WHERE id_utilisateur = ?", (id_utilisateur,))
    db.commit()

    enregistrer_action(db, "suppression_utilisateur", f"Utilisateur {utilisateur['email']} supprimé définitivement")
    flash("Utilisateur supprimé définitivement (et sa fiche employé associée, le cas échéant).", "success")
    return redirect(url_for("utilisateur.liste_utilisateurs"))