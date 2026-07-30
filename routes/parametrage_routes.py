# routes/parametrage_routes.py
from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from db import get_db
from utils.decorators import role_requis
from utils.journal import enregistrer_action
from utils.historique import enregistrer_modification, enregistrer_modification_multi

parametrage_bp = Blueprint("parametrage", __name__, url_prefix="/parametrage-global")


@parametrage_bp.route("/")
@role_requis("super_admin")
def vue_ensemble():
    db = get_db()
    baremes = db.execute("SELECT * FROM bareme_cotisation WHERE id_societe IS NULL ORDER BY code").fetchall()
    tranches = db.execute("SELECT * FROM tranche_ir WHERE id_societe IS NULL ORDER BY seuil_bas").fetchall()
    parametres = db.execute("SELECT * FROM parametre_legal WHERE id_societe IS NULL ORDER BY code").fetchall()
    elements = db.execute("SELECT * FROM element_paie WHERE id_societe IS NULL ORDER BY type_element, libelle").fetchall()
    return render_template(
        "parametrage/vue_ensemble.html",
        baremes=baremes, tranches=tranches, parametres=parametres, elements=elements,
    )


# ============================================================
# PAGE DE MODIFICATION - BAREME (GET)
# ============================================================
@parametrage_bp.route("/bareme/<int:id_bareme>/modifier", methods=["GET"])
@role_requis("super_admin")
def modifier_bareme_page(id_bareme):
    db = get_db()
    bareme = db.execute("SELECT * FROM bareme_cotisation WHERE id_bareme = ?", (id_bareme,)).fetchone()
    if bareme is None:
        flash("Barème introuvable.", "error")
        return redirect(url_for("parametrage.vue_ensemble"))
    
    return render_template("parametrage/formulaire_bareme.html", bareme=bareme)


# ============================================================
# ENREGISTREMENT - BAREME (POST)
# ============================================================
@parametrage_bp.route("/bareme/<int:id_bareme>/modifier", methods=["POST"])
@role_requis("super_admin")
def modifier_bareme(id_bareme):
    db = get_db()
    bareme = db.execute("SELECT * FROM bareme_cotisation WHERE id_bareme = ?", (id_bareme,)).fetchone()
    if bareme is None:
        flash("Barème introuvable.", "error")
        return redirect(url_for("parametrage.vue_ensemble"))

    # Récupérer les anciennes valeurs
    ancien_taux_salarial = bareme["taux_salarial"]
    ancien_taux_patronal = bareme["taux_patronal"]
    ancien_plafond = bareme["plafond_mensuel"]

    # Récupérer les nouvelles valeurs
    taux_salarial = request.form.get("taux_salarial")
    taux_patronal = request.form.get("taux_patronal")
    plafond_mensuel = request.form.get("plafond_mensuel")

    # Construire les modifications
    modifications = {}
    if taux_salarial is not None and taux_salarial != '':
        nouvelles = float(taux_salarial)
        if ancien_taux_salarial != nouvelles:
            modifications["taux_salarial"] = (ancien_taux_salarial, nouvelles)
    
    if taux_patronal is not None and taux_patronal != '':
        nouvelles = float(taux_patronal) if taux_patronal else None
        if ancien_taux_patronal != nouvelles:
            modifications["taux_patronal"] = (ancien_taux_patronal, nouvelles)
    
    if plafond_mensuel is not None and plafond_mensuel != '':
        nouvelles = float(plafond_mensuel) if plafond_mensuel else None
        if ancien_plafond != nouvelles:
            modifications["plafond_mensuel"] = (ancien_plafond, nouvelles)

    if not modifications:
        flash("Aucune modification fournie.", "warning")
        return redirect(url_for("parametrage.vue_ensemble"))

    # Mettre à jour la base
    updates = []
    params = []
    for champ, (ancien, nouveau) in modifications.items():
        if champ == "taux_salarial":
            updates.append("taux_salarial = ?")
            params.append(nouveau)
        elif champ == "taux_patronal":
            updates.append("taux_patronal = ?")
            params.append(nouveau)
        elif champ == "plafond_mensuel":
            updates.append("plafond_mensuel = ?")
            params.append(nouveau)
    
    params.append(id_bareme)
    db.execute(
        f"UPDATE bareme_cotisation SET {', '.join(updates)} WHERE id_bareme = ?",
        params
    )
    db.commit()

    # Enregistrer l'historique
    enregistrer_modification_multi(
        session["id_utilisateur"],
        None,  # id_societe = NULL pour global
        "bareme_cotisation",
        id_bareme,
        bareme["code"],
        modifications
    )

    enregistrer_action(db, "modification_bareme_global", f"Barème {bareme['code']} modifié")
    flash(f"Barème {bareme['code']} mis à jour.", "success")
    return redirect(url_for("parametrage.vue_ensemble"))



# ============================================================
# PAGE DE MODIFICATION - PARAMETRE (GET)
# ============================================================
@parametrage_bp.route("/parametre/<int:id_parametre>/modifier", methods=["GET"])
@role_requis("super_admin")
def modifier_parametre_page(id_parametre):
    db = get_db()
    parametre = db.execute("SELECT * FROM parametre_legal WHERE id_parametre = ?", (id_parametre,)).fetchone()
    if parametre is None:
        flash("Paramètre introuvable.", "error")
        return redirect(url_for("parametrage.vue_ensemble"))
    
    return render_template("parametrage/formulaire_parametre.html", parametre=parametre)


# ============================================================
# ENREGISTREMENT - PARAMETRE (POST)
# ============================================================
@parametrage_bp.route("/parametre/<int:id_parametre>/modifier", methods=["POST"])
@role_requis("super_admin")
def modifier_parametre(id_parametre):
    db = get_db()
    parametre = db.execute("SELECT * FROM parametre_legal WHERE id_parametre = ?", (id_parametre,)).fetchone()
    if parametre is None:
        flash("Paramètre introuvable.", "error")
        return redirect(url_for("parametrage.vue_ensemble"))

    ancienne_valeur = parametre["valeur"]
    nouvelle_valeur = request.form.get("valeur")

    if not nouvelle_valeur or nouvelle_valeur == '':
        flash("Valeur invalide.", "error")
        return redirect(url_for("parametrage.vue_ensemble"))

    nouvelle_valeur = float(nouvelle_valeur)
    
    if ancienne_valeur == nouvelle_valeur:
        flash("Aucune modification.", "warning")
        return redirect(url_for("parametrage.vue_ensemble"))

    db.execute(
        "UPDATE parametre_legal SET valeur = ? WHERE id_parametre = ?",
        (nouvelle_valeur, id_parametre)
    )
    db.commit()

    # Enregistrer l'historique
    enregistrer_modification(
        session["id_utilisateur"],
        None,
        "parametre_legal",
        id_parametre,
        parametre["code"],
        "valeur",
        ancienne_valeur,
        nouvelle_valeur
    )

    enregistrer_action(db, "modification_parametre_global", f"Paramètre {parametre['code']} modifié -> {nouvelle_valeur}")
    flash(f"Paramètre {parametre['code']} mis à jour.", "success")
    return redirect(url_for("parametrage.vue_ensemble"))


# ============================================================
# MODIFICATION - TRANCHES IR
# ============================================================
@parametrage_bp.route("/tranches-ir/modifier", methods=["GET", "POST"])
@role_requis("super_admin")
def modifier_tranches_ir():
    db = get_db()
    
    if request.method == "POST":
        tranches = db.execute("SELECT * FROM tranche_ir WHERE id_societe IS NULL ORDER BY seuil_bas").fetchall()
        
        for tranche in tranches:
            id_tranche = tranche["id_tranche"]
            seuil_bas = request.form.get(f"seuil_bas_{id_tranche}")
            seuil_haut = request.form.get(f"seuil_haut_{id_tranche}")
            taux = request.form.get(f"taux_{id_tranche}")
            somme_a_deduire = request.form.get(f"somme_a_deduire_{id_tranche}")
            
            if seuil_bas and taux is not None:
                db.execute(
                    """UPDATE tranche_ir 
                       SET seuil_bas = ?, seuil_haut = ?, taux = ?, somme_a_deduire = ?
                       WHERE id_tranche = ?""",
                    (
                        float(seuil_bas),
                        float(seuil_haut) if seuil_haut else None,
                        float(taux),
                        float(somme_a_deduire) if somme_a_deduire else 0,
                        id_tranche
                    )
                )
        
        db.commit()
        enregistrer_action(db, "modification_tranches_ir", "Barème IR global modifié")
        flash("Barème IR mis à jour avec succès.", "success")
        return redirect(url_for("parametrage.vue_ensemble"))
    
    tranches = db.execute("SELECT * FROM tranche_ir WHERE id_societe IS NULL ORDER BY seuil_bas").fetchall()
    return render_template("parametrage/modifier_tranches.html", tranches=tranches)


# ============================================================
# PAGE DE MODIFICATION - ELEMENT (GET)
# ============================================================
@parametrage_bp.route("/element/<int:id_element>/modifier", methods=["GET"])
@role_requis("super_admin")
def modifier_element_page(id_element):
    db = get_db()
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe IS NULL",
        (id_element,)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable.", "error")
        return redirect(url_for("parametrage.vue_ensemble"))
    
    return render_template("parametrage/formulaire_element.html", element=element)


# ============================================================
# ENREGISTREMENT - ELEMENT (POST)
# ============================================================
@parametrage_bp.route("/element/<int:id_element>/modifier", methods=["POST"])
@role_requis("super_admin")
def modifier_element_global(id_element):
    db = get_db()
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe IS NULL",
        (id_element,)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable.", "error")
        return redirect(url_for("parametrage.vue_ensemble"))
    
    db.execute(
        """UPDATE element_paie
           SET code = ?, libelle = ?, type_element = ?, mode_calcul = ?,
               valeur = ?, plafond_exoneration = ?, soumis_cnss = ?, soumis_ir = ?
           WHERE id_element = ? AND id_societe IS NULL""",
        (
            request.form["code"],
            request.form["libelle"],
            request.form["type_element"],
            request.form["mode_calcul"],
            float(request.form["valeur"]) if request.form.get("valeur") else None,
            float(request.form["plafond_exoneration"]) if request.form.get("plafond_exoneration") else None,
            1 if request.form.get("soumis_cnss") else 0,
            1 if request.form.get("soumis_ir") else 0,
            id_element
        )
    )
    db.commit()
    enregistrer_action(db, "modification_element_global", f"Élément modifié : {request.form['code']}")
    flash("Élément mis à jour.", "success")
    return redirect(url_for("parametrage.vue_ensemble"))


# ============================================================
# NOUVEL ELEMENT (GET + POST)
# ============================================================
@parametrage_bp.route("/element/nouveau", methods=["GET", "POST"])
@role_requis("super_admin")
def nouvel_element_global():
    if request.method == "POST":
        db = get_db()
        db.execute(
            """INSERT INTO element_paie
               (id_societe, code, libelle, type_element, mode_calcul, valeur,
                plafond_exoneration, soumis_cnss, soumis_ir, obligatoire)
               VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
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
        enregistrer_action(db, "creation_element_global", f"Élément créé : {request.form['code']}")
        flash("Élément ajouté au catalogue global.", "success")
        return redirect(url_for("parametrage.vue_ensemble"))

    return render_template("parametrage/formulaire_element.html")


# ============================================================
# SUPPRESSION ELEMENT (POST)
# ============================================================
@parametrage_bp.route("/element/<int:id_element>/supprimer", methods=["POST"])
@role_requis("super_admin")
def supprimer_element_global(id_element):
    db = get_db()
    element = db.execute(
        "SELECT * FROM element_paie WHERE id_element = ? AND id_societe IS NULL",
        (id_element,)
    ).fetchone()
    
    if element is None:
        flash("Élément introuvable.", "error")
        return redirect(url_for("parametrage.vue_ensemble"))
    
    db.execute("DELETE FROM element_paie WHERE id_element = ? AND id_societe IS NULL", (id_element,))
    db.commit()
    enregistrer_action(db, "suppression_element_global", f"Élément supprimé : {element['code']}")
    flash("Élément supprimé du catalogue global.", "success")
    return redirect(url_for("parametrage.vue_ensemble"))