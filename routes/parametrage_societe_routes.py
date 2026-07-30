# routes/parametrage_societe_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
from utils.decorators import role_requis, societe_requise
from utils.journal import enregistrer_action

parametrage_societe_bp = Blueprint("parametrage_societe", __name__, url_prefix="/mon-parametrage")


@parametrage_societe_bp.route("/")
@role_requis("admin_societe")
@societe_requise
def vue_ensemble():
    db = get_db()
    id_societe = session["id_societe"]
    
    baremes = db.execute(
        """SELECT * FROM bareme_cotisation 
           WHERE id_societe = ? OR id_societe IS NULL
           ORDER BY id_societe DESC, code""",
        (id_societe,)
    ).fetchall()
    
    tranches = db.execute(
        """SELECT * FROM tranche_ir 
           WHERE id_societe = ? OR id_societe IS NULL
           ORDER BY id_societe DESC, seuil_bas""",
        (id_societe,)
    ).fetchall()
    
    parametres = db.execute(
        """SELECT * FROM parametre_legal 
           WHERE id_societe = ? OR id_societe IS NULL
           ORDER BY id_societe DESC, code""",
        (id_societe,)
    ).fetchall()
    
    elements = db.execute(
        """SELECT * FROM element_paie 
           WHERE id_societe = ? OR id_societe IS NULL
           ORDER BY id_societe DESC, type_element, libelle""",
        (id_societe,)
    ).fetchall()
    
    societe = db.execute(
        "SELECT raison_sociale FROM societe WHERE id_societe = ?",
        (id_societe,)
    ).fetchone()
    
    return render_template(
        "parametrage_societe/vue_ensemble.html",
        baremes=baremes,
        tranches=tranches,
        parametres=parametres,
        elements=elements,
        societe=societe
    )


# ============================================================
# PAGE DE MODIFICATION - BAREME (GET)
# ============================================================
@parametrage_societe_bp.route("/bareme/<int:id_bareme>/modifier-page", methods=["GET"])
@role_requis("admin_societe")
@societe_requise
def modifier_bareme_page(id_bareme):
    db = get_db()
    id_societe = session["id_societe"]
    
    bareme = db.execute(
        "SELECT * FROM bareme_cotisation WHERE id_bareme = ? AND (id_societe = ? OR id_societe IS NULL)",
        (id_bareme, id_societe)
    ).fetchone()
    
    if bareme is None:
        flash("Barème introuvable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    return render_template("parametrage_societe/formulaire_bareme.html", bareme=bareme)


# ============================================================
# ENREGISTREMENT - BAREME (POST)
# ============================================================
@parametrage_societe_bp.route("/bareme/<int:id_bareme>/modifier-page", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def modifier_bareme_page_post(id_bareme):
    db = get_db()
    id_societe = session["id_societe"]
    
    bareme = db.execute(
        "SELECT * FROM bareme_cotisation WHERE id_bareme = ? AND (id_societe = ? OR id_societe IS NULL)",
        (id_bareme, id_societe)
    ).fetchone()
    
    if bareme is None:
        flash("Barème introuvable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    # Si c'est un barème global, on crée une copie spécifique
    if bareme["id_societe"] is None:
        db.execute(
            """INSERT INTO bareme_cotisation (id_societe, code, libelle, taux_salarial, taux_patronal, plafond_mensuel, annee_application)
               SELECT ?, code, libelle, taux_salarial, taux_patronal, plafond_mensuel, annee_application
               FROM bareme_cotisation WHERE id_bareme = ?""",
            (id_societe, id_bareme)
        )
        new_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        id_bareme = new_id
    
    db.execute(
        """UPDATE bareme_cotisation 
           SET taux_salarial = ?, taux_patronal = ?, plafond_mensuel = ?
           WHERE id_bareme = ? AND id_societe = ?""",
        (
            float(request.form["taux_salarial"]),
            float(request.form["taux_patronal"]) if request.form.get("taux_patronal") else None,
            float(request.form["plafond_mensuel"]) if request.form.get("plafond_mensuel") else None,
            id_bareme,
            id_societe
        )
    )
    db.commit()
    enregistrer_action(db, "modification_bareme_societe", f"Barème modifié pour la société {id_societe}")
    flash("Barème mis à jour pour votre société.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))


# ============================================================
# PAGE DE MODIFICATION - PARAMETRE (GET)
# ============================================================
@parametrage_societe_bp.route("/parametre/<int:id_parametre>/modifier-page", methods=["GET"])
@role_requis("admin_societe")
@societe_requise
def modifier_parametre_page(id_parametre):
    db = get_db()
    id_societe = session["id_societe"]
    
    parametre = db.execute(
        "SELECT * FROM parametre_legal WHERE id_parametre = ? AND (id_societe = ? OR id_societe IS NULL)",
        (id_parametre, id_societe)
    ).fetchone()
    
    if parametre is None:
        flash("Paramètre introuvable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    return render_template("parametrage_societe/formulaire_parametre.html", parametre=parametre)


# ============================================================
# ENREGISTREMENT - PARAMETRE (POST)
# ============================================================
@parametrage_societe_bp.route("/parametre/<int:id_parametre>/modifier-page", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def modifier_parametre_page_post(id_parametre):
    db = get_db()
    id_societe = session["id_societe"]
    
    parametre = db.execute(
        "SELECT * FROM parametre_legal WHERE id_parametre = ? AND (id_societe = ? OR id_societe IS NULL)",
        (id_parametre, id_societe)
    ).fetchone()
    
    if parametre is None:
        flash("Paramètre introuvable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    # Si c'est un paramètre global, on crée une copie spécifique
    if parametre["id_societe"] is None:
        db.execute(
            """INSERT INTO parametre_legal (id_societe, code, libelle, valeur, unite, annee_application)
               SELECT ?, code, libelle, valeur, unite, annee_application
               FROM parametre_legal WHERE id_parametre = ?""",
            (id_societe, id_parametre)
        )
        new_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        id_parametre = new_id
    
    db.execute(
        "UPDATE parametre_legal SET valeur = ? WHERE id_parametre = ? AND id_societe = ?",
        (float(request.form["valeur"]), id_parametre, id_societe)
    )
    db.commit()
    enregistrer_action(db, "modification_parametre_societe", f"Paramètre modifié pour la société {id_societe}")
    flash("Paramètre mis à jour pour votre société.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))


# ============================================================
# SUPPRIMER - BAREME PERSONNALISE
# ============================================================
@parametrage_societe_bp.route("/bareme/<int:id_bareme>/supprimer", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def supprimer_bareme(id_bareme):
    db = get_db()
    id_societe = session["id_societe"]
    
    bareme = db.execute(
        "SELECT * FROM bareme_cotisation WHERE id_bareme = ? AND id_societe = ?",
        (id_bareme, id_societe)
    ).fetchone()
    
    if bareme is None:
        flash("Barème introuvable ou non supprimable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    db.execute("DELETE FROM bareme_cotisation WHERE id_bareme = ? AND id_societe = ?", (id_bareme, id_societe))
    db.commit()
    enregistrer_action(db, "suppression_bareme_societe", f"Barème supprimé pour la société {id_societe}")
    flash("Barème supprimé de votre société.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))


# ============================================================
# SUPPRIMER - PARAMETRE PERSONNALISE
# ============================================================
@parametrage_societe_bp.route("/parametre/<int:id_parametre>/supprimer", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def supprimer_parametre(id_parametre):
    db = get_db()
    id_societe = session["id_societe"]
    
    parametre = db.execute(
        "SELECT * FROM parametre_legal WHERE id_parametre = ? AND id_societe = ?",
        (id_parametre, id_societe)
    ).fetchone()
    
    if parametre is None:
        flash("Paramètre introuvable ou non supprimable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    db.execute("DELETE FROM parametre_legal WHERE id_parametre = ? AND id_societe = ?", (id_parametre, id_societe))
    db.commit()
    enregistrer_action(db, "suppression_parametre_societe", f"Paramètre supprimé pour la société {id_societe}")
    flash("Paramètre supprimé de votre société.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))


# ============================================================
# MODIFICATION - ELEMENT
# ============================================================
@parametrage_societe_bp.route("/element/<int:id_element>/modifier", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def modifier_element(id_element):
    db = get_db()
    id_societe = session["id_societe"]
    
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND (id_societe = ? OR id_societe IS NULL)",
        (id_element, id_societe)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    # Si c'est un élément global, on crée une copie spécifique
    if element["id_societe"] is None:
        db.execute(
            """INSERT INTO element_paie (id_societe, code, libelle, type_element, mode_calcul, valeur, plafond_exoneration, soumis_cnss, soumis_ir, obligatoire)
               SELECT ?, code, libelle, type_element, mode_calcul, valeur, plafond_exoneration, soumis_cnss, soumis_ir, obligatoire
               FROM element_paie WHERE id_element = ?""",
            (id_societe, id_element)
        )
        new_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        id_element = new_id
    
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
    enregistrer_action(db, "modification_element_societe", f"Élément modifié pour la société {id_societe}")
    flash("Élément mis à jour pour votre société.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))


# ============================================================
# SUPPRESSION - ELEMENT
# ============================================================
@parametrage_societe_bp.route("/element/<int:id_element>/supprimer", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def supprimer_element(id_element):
    db = get_db()
    id_societe = session["id_societe"]
    
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe = ?",
        (id_element, id_societe)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable ou non modifiable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    db.execute("DELETE FROM element_paie WHERE id_element = ? AND id_societe = ?", (id_element, id_societe))
    db.commit()
    enregistrer_action(db, "suppression_element_societe", f"Élément supprimé pour la société {id_societe}")
    flash("Élément supprimé de votre catalogue.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))


# ============================================================
# COPIER UN ELEMENT LEGAL DANS LA SOCIETE
# ============================================================
@parametrage_societe_bp.route("/element/<int:id_element>/copier", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def copier_element(id_element):
    db = get_db()
    id_societe = session["id_societe"]
    
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe IS NULL",
        (id_element,)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    existant = db.execute(
        "SELECT * FROM element_paie WHERE code = ? AND id_societe = ?",
        (element["code"], id_societe)
    ).fetchone()
    
    if existant:
        flash("Cet élément existe déjà dans votre société.", "warning")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
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
    return redirect(url_for("parametrage_societe.vue_ensemble"))


# ============================================================
# AJOUTER UN NOUVEL ELEMENT
# ============================================================
@parametrage_societe_bp.route("/element/nouveau", methods=["GET", "POST"])
@role_requis("admin_societe")
@societe_requise
def nouvel_element():
    if request.method == "POST":
        db = get_db()
        id_societe = session["id_societe"]
        
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
        return redirect(url_for("parametrage_societe.vue_ensemble"))

    return render_template("parametrage_societe/formulaire_element.html")


# ============================================================
# MODIFICATION - TRANCHE IR
# ============================================================
@parametrage_societe_bp.route("/tranche/<int:id_tranche>/modifier", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def modifier_tranche(id_tranche):
    db = get_db()
    id_societe = session["id_societe"]
    
    tranche = db.execute(
        "SELECT * FROM tranche_ir WHERE id_tranche = ? AND (id_societe = ? OR id_societe IS NULL)",
        (id_tranche, id_societe)
    ).fetchone()
    
    if tranche is None:
        flash("Tranche IR introuvable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    if tranche["id_societe"] is None:
        db.execute(
            """INSERT INTO tranche_ir (id_societe, seuil_bas, seuil_haut, taux, somme_a_deduire, annee_application)
               SELECT ?, seuil_bas, seuil_haut, taux, somme_a_deduire, annee_application
               FROM tranche_ir WHERE id_tranche = ?""",
            (id_societe, id_tranche)
        )
        new_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        id_tranche = new_id
    
    db.execute(
        """UPDATE tranche_ir 
           SET seuil_bas = ?, seuil_haut = ?, taux = ?, somme_a_deduire = ?
           WHERE id_tranche = ? AND id_societe = ?""",
        (
            float(request.form["seuil_bas"]),
            float(request.form["seuil_haut"]) if request.form.get("seuil_haut") else None,
            float(request.form["taux"]),
            float(request.form["somme_a_deduire"]) if request.form.get("somme_a_deduire") else 0,
            id_tranche,
            id_societe
        )
    )
    db.commit()
    enregistrer_action(db, "modification_tranche_societe", f"Tranche IR modifiée pour la société {id_societe}")
    flash("Tranche IR mise à jour pour votre société.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))


# ============================================================
# COPIER - TRANCHE IR DANS LA SOCIETE
# ============================================================
@parametrage_societe_bp.route("/tranche/<int:id_tranche>/copier", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def copier_tranche(id_tranche):
    db = get_db()
    id_societe = session["id_societe"]
    
    tranche = db.execute(
        "SELECT * FROM tranche_ir WHERE id_tranche = ? AND id_societe IS NULL",
        (id_tranche,)
    ).fetchone()
    
    if tranche is None:
        flash("Tranche IR introuvable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    existant = db.execute(
        "SELECT * FROM tranche_ir WHERE seuil_bas = ? AND id_societe = ?",
        (tranche["seuil_bas"], id_societe)
    ).fetchone()
    
    if existant:
        flash("Cette tranche existe déjà dans votre société.", "warning")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    db.execute(
        """INSERT INTO tranche_ir 
           (id_societe, seuil_bas, seuil_haut, taux, somme_a_deduire, annee_application)
           SELECT ?, seuil_bas, seuil_haut, taux, somme_a_deduire, annee_application
           FROM tranche_ir WHERE id_tranche = ?""",
        (id_societe, id_tranche)
    )
    db.commit()
    
    enregistrer_action(db, "copier_tranche_societe", f"Tranche IR copiée dans la société {id_societe}")
    flash("Tranche IR copiée dans votre société. Vous pouvez maintenant la modifier.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))


# ============================================================
# SUPPRIMER - TRANCHE IR PERSONNALISEE
# ============================================================
@parametrage_societe_bp.route("/tranche/<int:id_tranche>/supprimer", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def supprimer_tranche(id_tranche):
    db = get_db()
    id_societe = session["id_societe"]
    
    tranche = db.execute(
        "SELECT * FROM tranche_ir WHERE id_tranche = ? AND id_societe = ?",
        (id_tranche, id_societe)
    ).fetchone()
    
    if tranche is None:
        flash("Tranche IR introuvable ou non supprimable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    db.execute("DELETE FROM tranche_ir WHERE id_tranche = ? AND id_societe = ?", (id_tranche, id_societe))
    db.commit()
    enregistrer_action(db, "suppression_tranche_societe", f"Tranche IR supprimée pour la société {id_societe}")
    flash("Tranche IR supprimée de votre société.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))

# ============================================================
# PAGE DE MODIFICATION - ELEMENT (GET)
# ============================================================
@parametrage_societe_bp.route("/element/<int:id_element>/modifier-page", methods=["GET"])
@role_requis("admin_societe")
@societe_requise
def modifier_element_page(id_element):
    db = get_db()
    id_societe = session["id_societe"]
    
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe = ?",
        (id_element, id_societe)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable ou non modifiable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
    return render_template("parametrage_societe/formulaire_element_modifier.html", element=element)


# ============================================================
# ENREGISTREMENT - ELEMENT (POST)
# ============================================================
@parametrage_societe_bp.route("/element/<int:id_element>/modifier-page", methods=["POST"])
@role_requis("admin_societe")
@societe_requise
def modifier_element_page_post(id_element):
    db = get_db()
    id_societe = session["id_societe"]
    
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe = ?",
        (id_element, id_societe)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable.", "error")
        return redirect(url_for("parametrage_societe.vue_ensemble"))
    
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
    flash("Élément mis à jour pour votre société.", "success")
    return redirect(url_for("parametrage_societe.vue_ensemble"))