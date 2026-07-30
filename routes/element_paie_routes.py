# routes/element_paie_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
from utils.decorators import role_requis, societe_requise
from utils.journal import enregistrer_action

element_bp = Blueprint("element", __name__, url_prefix="/elements")


@element_bp.route("/")
@role_requis("admin_societe", "rh", "comptable")
@societe_requise
def liste_elements():
    db = get_db()
    id_societe = session.get("id_societe")
    
    # Afficher les éléments légaux + les éléments de la société
    elements = db.execute(
        """SELECT * FROM element_paie 
           WHERE id_societe IS NULL OR id_societe = ?
           ORDER BY id_societe DESC, type_element, libelle""",
        (id_societe,)
    ).fetchall()
    
    return render_template("elements/liste.html", elements=elements)


# ============================================================
# COPIER UN ELEMENT LEGAL DANS LA SOCIETE
# ============================================================
@element_bp.route("/copier/<int:id_element>", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def copier_element_societe(id_element):
    db = get_db()
    id_societe = session.get("id_societe")
    
    # Vérifier que l'élément existe et est légal
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe IS NULL",
        (id_element,)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable.", "error")
        return redirect(url_for("element.liste_elements"))
    
    # Vérifier si l'élément existe déjà dans la société
    existant = db.execute(
        "SELECT * FROM element_paie WHERE code = ? AND id_societe = ?",
        (element["code"], id_societe)
    ).fetchone()
    
    if existant:
        flash("Cet élément existe déjà dans votre société.", "warning")
        return redirect(url_for("element.liste_elements"))
    
    # Copier l'élément dans la société
    db.execute(
        """INSERT INTO element_paie 
           (id_societe, code, libelle, type_element, mode_calcul, 
            valeur, plafond_exoneration, soumis_cnss, soumis_ir, obligatoire)
           SELECT ?, code, libelle, type_element, mode_calcul, 
                  valeur, plafond_exoneration, soumis_cnss, soumis_ir, obligatoire
           FROM element_paie WHERE id_element = ?""",
        (id_societe, id_element)
    )
    db.commit()
    
    enregistrer_action(db, "copier_element_societe", f"Élément {element['code']} copié dans la société {id_societe}")
    flash("Élément copié dans votre catalogue. Vous pouvez maintenant le modifier.", "success")
    return redirect(url_for("element.liste_elements"))


# ============================================================
# MODIFIER UN ELEMENT DE LA SOCIETE
# ============================================================
@element_bp.route("/modifier/<int:id_element>", methods=["GET", "POST"])
@role_requis("admin_societe")
@societe_requise
def modifier_element_societe(id_element):
    db = get_db()
    id_societe = session.get("id_societe")
    
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe = ?",
        (id_element, id_societe)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable ou non modifiable.", "error")
        return redirect(url_for("element.liste_elements"))
    
    if request.method == "POST":
        db.execute(
            """UPDATE element_paie
               SET code = ?, libelle = ?, type_element = ?, mode_calcul = ?,
                   valeur = ?, plafond_exoneration = ?, soumis_cnss = ?, soumis_ir = ?
               WHERE id_element = ? AND id_societe = ?""",
            (
                request.form["code"],
                request.form["libelle"],
                request.form["type_element"],
                request.form["mode_calcul"],
                float(request.form["valeur"]) if request.form.get("valeur") else None,
                float(request.form["plafond_exoneration"]) if request.form.get("plafond_exoneration") else None,
                1 if request.form.get("soumis_cnss") else 0,
                1 if request.form.get("soumis_ir") else 0,
                id_element,
                id_societe
            )
        )
        db.commit()
        enregistrer_action(db, "modification_element_societe", f"Élément modifié : {request.form['code']}")
        flash("Élément mis à jour.", "success")
        return redirect(url_for("element.liste_elements"))
    
    return render_template("elements/formulaire_societe.html", element=element)


# ============================================================
# SUPPRIMER UN ELEMENT DE LA SOCIETE
# ============================================================
@element_bp.route("/supprimer/<int:id_element>", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def supprimer_element_societe(id_element):
    db = get_db()
    id_societe = session.get("id_societe")
    
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe = ?",
        (id_element, id_societe)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable.", "error")
        return redirect(url_for("element.liste_elements"))
    
    db.execute("DELETE FROM element_paie WHERE id_element = ? AND id_societe = ?", (id_element, id_societe))
    db.commit()
    
    enregistrer_action(db, "suppression_element_societe", f"Élément supprimé : {element['code']}")
    flash("Élément supprimé de votre catalogue.", "success")
    return redirect(url_for("element.liste_elements"))


# ============================================================
# AJOUTER UN NOUVEL ELEMENT POUR LA SOCIETE
# ============================================================
@element_bp.route("/nouveau", methods=["GET", "POST"])
@role_requis("admin_societe")
@societe_requise
def nouvel_element_societe():
    if request.method == "POST":
        db = get_db()
        id_societe = session.get("id_societe")
        
        db.execute(
            """INSERT INTO element_paie
               (id_societe, code, libelle, type_element, mode_calcul, valeur,
                plafond_exoneration, soumis_cnss, soumis_ir, obligatoire)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                id_societe,
                request.form["code"],
                request.form["libelle"],
                request.form["type_element"],
                request.form["mode_calcul"],
                float(request.form["valeur"]) if request.form.get("valeur") else None,
                float(request.form["plafond_exoneration"]) if request.form.get("plafond_exoneration") else None,
                1 if request.form.get("soumis_cnss") else 0,
                1 if request.form.get("soumis_ir") else 0,
            ),
        )
        db.commit()
        enregistrer_action(db, "creation_element_societe", f"Élément créé : {request.form['code']}")
        flash("Élément ajouté à votre catalogue.", "success")
        return redirect(url_for("element.liste_elements"))

    return render_template("elements/formulaire_societe.html")