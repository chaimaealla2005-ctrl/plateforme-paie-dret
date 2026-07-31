from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort, make_response
from db import get_db
from utils.decorators import role_requis, societe_requise
from moteur_paie import calculer_bulletin
from utils.journal import enregistrer_action
import pdfkit
import os
import math
from utils.export import export_bulletins, export_to_csv, export_to_excel

bulletin_bp = Blueprint("bulletin", __name__, url_prefix="/bulletins")
WKHTMLTOPDF_PATH = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'

if not os.path.exists(WKHTMLTOPDF_PATH):
    # Essayer un chemin alternatif
    alt_path = r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe'
    if os.path.exists(alt_path):
        WKHTMLTOPDF_PATH = alt_path
    else:
        # Si tu n'as pas installé wkhtmltopdf, utiliser une configuration sans chemin
        # (espérant qu'il soit dans le PATH)
        WKHTMLTOPDF_PATH = None
        print("⚠️ wkhtmltopdf non trouvé. Assure-toi qu'il est installé et dans le PATH.")

# Configuration de pdfkit
def get_pdfkit_config():
    if WKHTMLTOPDF_PATH:
        return pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
    return None

def _charger_baremes_cotisation(db, id_societe):
    """Recupere les baremes CNSS/AMO : priorite a la regle de la societe,
    sinon on retombe sur la regle legale par defaut (id_societe IS NULL)."""
    rows = db.execute(
        """SELECT * FROM bareme_cotisation
           WHERE id_societe = ? OR id_societe IS NULL
           ORDER BY code""",
        (id_societe,),
    ).fetchall()

    baremes_par_code = {}
    for row in rows:
        code = row["code"]
        if code not in baremes_par_code or row["id_societe"] is not None:
            baremes_par_code[code] = dict(row)
    return list(baremes_par_code.values())


def _charger_tranches_ir(db, id_societe):
    tranches_societe = db.execute(
        "SELECT * FROM tranche_ir WHERE id_societe = ? ORDER BY seuil_bas", (id_societe,)
    ).fetchall()
    if tranches_societe:
        return [dict(t) for t in tranches_societe]
    tranches_globales = db.execute(
        "SELECT * FROM tranche_ir WHERE id_societe IS NULL ORDER BY seuil_bas"
    ).fetchall()
    return [dict(t) for t in tranches_globales]


def _charger_parametres_legaux(db, id_societe):
    rows = db.execute(
        "SELECT * FROM parametre_legal WHERE id_societe = ? OR id_societe IS NULL",
        (id_societe,),
    ).fetchall()
    parametres = {}
    for row in rows:
        if row["code"] not in parametres or row["id_societe"] is not None:
            parametres[row["code"]] = row["valeur"]
    return parametres


# routes/bulletin_routes.py - Fonction _charger_elements_employe MODIFIEE

def _charger_elements_employe(db, id_employe):
    """Recupere tous les elements de paie (primes/indemnites) actifs
    affectes a cet employe, avec leurs paliers eventuels.
    Si la prime d'ancienneté n'est pas affectée, elle est ajoutée automatiquement.
    """
    rows = db.execute(
        """SELECT ep.* FROM employe_element ee
           JOIN element_paie ep ON ep.id_element = ee.id_element
           WHERE ee.id_employe = ?
             AND (ee.date_fin IS NULL OR ee.date_fin >= date('now'))""",
        (id_employe,),
    ).fetchall()

    elements = []
    prime_trouvee = False
    
    for row in rows:
        element = dict(row)
        if element.get("code") == "PRIME_ANCIENNETE":
            prime_trouvee = True
        paliers = db.execute(
            "SELECT * FROM palier_element WHERE id_element = ? ORDER BY annees_min",
            (element["id_element"],),
        ).fetchall()
        elements.append({
            "element": element,
            "paliers": [dict(p) for p in paliers] if paliers else None,
        })
    
    # ============================================================
    # SI LA PRIME D'ANCIENNETE N'EST PAS AFFECTEE, L'AJOUTER
    # ============================================================
    if not prime_trouvee:
        prime = db.execute(
            "SELECT * FROM element_paie WHERE code = ?",
            ('PRIME_ANCIENNETE',)
        ).fetchone()
        if prime:
            paliers = db.execute(
                "SELECT * FROM palier_element WHERE id_element = ? ORDER BY annees_min",
                (prime["id_element"],),
            ).fetchall()
            elements.append({
                "element": dict(prime),
                "paliers": [dict(p) for p in paliers] if paliers else None,
            })
            print(f"✅ Prime d'ancienneté ajoutée automatiquement pour l'employé {id_employe}")
    
    return elements


# ============================================================
# LISTE DES BULLETINS (Admin Société / Comptable)
# ============================================================
# routes/bulletin_routes.py - Modifier la fonction liste_bulletins

@bulletin_bp.route("/")
@role_requis("admin_societe", "comptable")
@societe_requise
def liste_bulletins():
    db = get_db()
    id_societe = session.get("id_societe")
    
    # Récupérer les paramètres de pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if per_page > 100:
        per_page = 100
    
    # Récupérer les paramètres de filtrage
    filtre_recherche = request.args.get('recherche', '').strip()
    filtre_mois = request.args.get('mois', 'tous')
    filtre_annee = request.args.get('annee', 'tous')
    
    # Construction de la requête
    query = """SELECT bp.*, e.nom, e.prenom, e.matricule
               FROM bulletin_paie bp
               JOIN employe e ON e.id_employe = bp.id_employe
               WHERE e.id_societe = ?"""
    params = [id_societe]
    
    count_query = """SELECT COUNT(*) AS total FROM bulletin_paie bp
                     JOIN employe e ON e.id_employe = bp.id_employe
                     WHERE e.id_societe = ?"""
    count_params = [id_societe]
    
    if filtre_recherche:
        query += " AND (e.nom LIKE ? OR e.prenom LIKE ? OR e.matricule LIKE ?)"
        params.extend([f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%'])
        count_query += " AND (e.nom LIKE ? OR e.prenom LIKE ? OR e.matricule LIKE ?)"
        count_params.extend([f'%{filtre_recherche}%', f'%{filtre_recherche}%', f'%{filtre_recherche}%'])
    
    if filtre_mois != 'tous' and filtre_mois:
        query += " AND bp.mois = ?"
        params.append(int(filtre_mois))
        count_query += " AND bp.mois = ?"
        count_params.append(int(filtre_mois))
    
    if filtre_annee != 'tous' and filtre_annee:
        query += " AND bp.annee = ?"
        params.append(int(filtre_annee))
        count_query += " AND bp.annee = ?"
        count_params.append(int(filtre_annee))
    
    # Obtenir le nombre total
    total = db.execute(count_query, count_params).fetchone()["total"]
    
    # Pagination
    offset = (page - 1) * per_page
    query += " ORDER BY bp.annee DESC, bp.mois DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    
    bulletins = db.execute(query, params).fetchall()
    
    # Créer l'objet pagination
    from utils.pagination import Pagination
    pagination = Pagination([], page, per_page)
    pagination.total = total
    pagination.total_pages = math.ceil(total / per_page) if total > 0 else 1
    pagination.current_items = bulletins
    
    # Statistiques
    total_bulletins = total
    total_masse_salariale = db.execute(
        """SELECT COALESCE(SUM(bp.salaire_net_a_payer), 0) AS total 
           FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ?""",
        (id_societe,)
    ).fetchone()["total"]
    
    # Années disponibles
    annees = db.execute(
        """SELECT DISTINCT bp.annee FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ?
           ORDER BY bp.annee DESC""",
        (id_societe,)
    ).fetchall()
    
    return render_template(
        "bulletins/liste.html",
        bulletins=bulletins,
        pagination=pagination,
        total_bulletins=total_bulletins,
        total_masse_salariale=total_masse_salariale,
        annees=annees,
        filtre_recherche=filtre_recherche,
        filtre_mois=filtre_mois,
        filtre_annee=filtre_annee
    )


# ============================================================
# GENERER UN BULLETIN
# ============================================================
@bulletin_bp.route("/generer/<int:id_employe>", methods=["GET", "POST"])
@role_requis("comptable", "admin_societe")
@societe_requise
def generer_bulletin(id_employe):
    db = get_db()
    id_societe = session["id_societe"]
    
    employe = db.execute(
        "SELECT * FROM employe WHERE id_employe = ? AND id_societe = ?",
        (id_employe, id_societe),
    ).fetchone()

    if employe is None:
        flash("Employé introuvable.", "error")
        return redirect(url_for("employe.liste_employes"))

    if request.method == "POST":
        mois = int(request.form["mois"])
        annee = int(request.form["annee"])

        # Vérifier si un bulletin existe déjà
        existant = db.execute(
            "SELECT * FROM bulletin_paie WHERE id_employe = ? AND mois = ? AND annee = ?",
            (id_employe, mois, annee)
        ).fetchone()
        
        if existant:
            flash("Un bulletin existe déjà pour ce mois.", "warning")
            return redirect(url_for("bulletin.detail_bulletin", id_bulletin=existant["id_bulletin"]))

        # Charger les règles
        baremes = _charger_baremes_cotisation(db, id_societe)
        tranches = _charger_tranches_ir(db, id_societe)
        parametres = _charger_parametres_legaux(db, id_societe)
        elements_employe = _charger_elements_employe(db, id_employe)

        # Calculer le bulletin
        resultat = calculer_bulletin(dict(employe), elements_employe, baremes, tranches, parametres)

        # Enregistrer le bulletin
        db.execute(
            """INSERT INTO bulletin_paie
               (id_employe, mois, annee, salaire_base, total_primes_indemnites,
                salaire_brut, total_cnss, total_amo, salaire_net_imposable,
                total_ir, salaire_net_a_payer)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                id_employe, mois, annee, resultat["salaire_base"], resultat["total_gains"],
                resultat["salaire_brut"], resultat["cotisations"].get("CNSS", 0),
                resultat["cotisations"].get("AMO", 0), resultat["salaire_net_imposable"],
                resultat["total_ir"], resultat["salaire_net_a_payer"],
            ),
        )
        id_bulletin = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # Enregistrer les lignes du bulletin
        lignes_inserees = 0
        
        # Salaire de base
        db.execute(
            """INSERT INTO ligne_bulletin (id_bulletin, libelle, montant, type_ligne)
               VALUES (?, ?, ?, 'gain')""",
            (id_bulletin, "Salaire de base", resultat["salaire_base"])
        )
        lignes_inserees += 1
        
        # Primes et indemnités
        for ligne in resultat["lignes_gains"]:
            if ligne["montant"] > 0:
                db.execute(
                    """INSERT INTO ligne_bulletin (id_bulletin, libelle, montant, type_ligne)
                       VALUES (?, ?, ?, 'gain')""",
                    (id_bulletin, ligne["libelle"], ligne["montant"])
                )
                lignes_inserees += 1

        # Cotisations
        for code, montant in resultat["cotisations"].items():
            if montant > 0:
                db.execute(
                    """INSERT INTO ligne_bulletin (id_bulletin, libelle, montant, type_ligne)
                       VALUES (?, ?, ?, 'cotisation')""",
                    (id_bulletin, code, -montant)
                )
                lignes_inserees += 1
        
        # Impôt
        if resultat["total_ir"] > 0:
            db.execute(
                """INSERT INTO ligne_bulletin (id_bulletin, libelle, montant, type_ligne)
                   VALUES (?, ?, ?, 'impot')""",
                (id_bulletin, "Impôt sur le Revenu (IR)", -resultat["total_ir"])
            )
            lignes_inserees += 1

        db.commit()
        enregistrer_action(db, "generation_bulletin", f"Bulletin généré pour employé {id_employe}")
        flash(f"Bulletin généré avec succès ({lignes_inserees} lignes).", "success")
        return redirect(url_for("bulletin.detail_bulletin", id_bulletin=id_bulletin))

    return render_template("bulletins/generer.html", employe=employe)


# ============================================================
# DETAIL D'UN BULLETIN (Admin Société / Comptable)
# ============================================================
@bulletin_bp.route("/<int:id_bulletin>")
@role_requis("comptable", "admin_societe", "employe")
@societe_requise
def detail_bulletin(id_bulletin):
    db = get_db()
    bulletin = db.execute(
        "SELECT * FROM bulletin_paie WHERE id_bulletin = ?", (id_bulletin,)
    ).fetchone()
    
    if bulletin is None:
        flash("Bulletin introuvable.", "error")
        return redirect(url_for("employe.liste_employes"))

    employe = db.execute(
        "SELECT * FROM employe WHERE id_employe = ?", (bulletin["id_employe"],)
    ).fetchone()

    # Vérifier les droits
    if session["role"] == "employe" and employe["id_utilisateur"] != session["id_utilisateur"]:
        abort(403)
    
    id_societe = session.get("id_societe")
    if session["role"] != "super_admin" and employe["id_societe"] != id_societe:
        abort(403)

    lignes = db.execute(
        "SELECT * FROM ligne_bulletin WHERE id_bulletin = ? ORDER BY id_ligne",
        (id_bulletin,)
    ).fetchall()

    return render_template("bulletins/detail.html", bulletin=bulletin, employe=employe, lignes=lignes)


# ============================================================
# MES BULLETINS (Employé)
# ============================================================
# routes/bulletin_routes.py

@bulletin_bp.route("/mon-bulletin")
@role_requis("employe", "rh", "comptable", "admin_societe", "super_admin")
def mon_bulletin():
    db = get_db()
    
    # Récupérer l'employé connecté
    employe = db.execute(
        "SELECT * FROM employe WHERE id_utilisateur = ?",
        (session["id_utilisateur"],)
    ).fetchone()
    
    # Si l'utilisateur n'a pas de fiche employé, lui en créer une automatiquement
    if employe is None:
        # Récupérer les infos de l'utilisateur
        utilisateur = db.execute(
            "SELECT * FROM utilisateur WHERE id_utilisateur = ?",
            (session["id_utilisateur"],)
        ).fetchone()
        
        if utilisateur:
            # Créer une fiche employé pour cet utilisateur
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
            
            # Recharger l'employé
            employe = db.execute(
                "SELECT * FROM employe WHERE id_utilisateur = ?",
                (session["id_utilisateur"],)
            ).fetchone()
            
            flash("✅ Une fiche employé a été automatiquement créée pour votre compte.", "success")
    
    if employe is None:
        flash("Aucun profil employé associé à ce compte. Veuillez contacter l'administrateur.", "error")
        return redirect(url_for("index"))
    
    bulletins = db.execute(
        """SELECT * FROM bulletin_paie 
           WHERE id_employe = ? 
           ORDER BY annee DESC, mois DESC""",
        (employe["id_employe"],)
    ).fetchall()
    
    return render_template("bulletins/mes_bulletins.html", bulletins=bulletins, employe=employe)

# ============================================================
# DETAIL D'UN BULLETIN (Employé)
# ============================================================
@bulletin_bp.route("/mon-bulletin/<int:id_bulletin>")
@role_requis("employe", "comptable", "rh", "admin_societe")
def mon_bulletin_detail(id_bulletin):
    db = get_db()
    
    employe = db.execute(
        "SELECT * FROM employe WHERE id_utilisateur = ?",
        (session["id_utilisateur"],)
    ).fetchone()
    
    if employe is None:
        flash("Aucun profil employé associé à ce compte.", "error")
        return redirect(url_for("index"))
    
    bulletin = db.execute(
        "SELECT * FROM bulletin_paie WHERE id_bulletin = ? AND id_employe = ?",
        (id_bulletin, employe["id_employe"])
    ).fetchone()
    
    if bulletin is None:
        flash("Bulletin introuvable ou accès non autorisé.", "error")
        return redirect(url_for("bulletin.mon_bulletin"))
    
    lignes = db.execute(
        "SELECT * FROM ligne_bulletin WHERE id_bulletin = ? ORDER BY id_ligne",
        (id_bulletin,)
    ).fetchall()
    
    return render_template(
        "bulletins/mon_bulletin_detail.html",
        bulletin=bulletin,
        lignes=lignes,
        employe=employe
    )


# ============================================================
# HISTORIQUE DES BULLETINS (Admin Société / RH / Comptable)
# ============================================================
@bulletin_bp.route("/historique/<int:id_employe>")
@role_requis("admin_societe", "rh", "comptable")
@societe_requise
def historique_bulletins(id_employe):
    db = get_db()
    id_societe = session.get("id_societe")
    
    employe = db.execute(
        "SELECT * FROM employe WHERE id_employe = ? AND id_societe = ?",
        (id_employe, id_societe)
    ).fetchone()
    
    if employe is None:
        flash("Employé introuvable.", "error")
        return redirect(url_for("employe.liste_employes"))
    
    bulletins = db.execute(
        "SELECT * FROM bulletin_paie WHERE id_employe = ? ORDER BY annee DESC, mois DESC",
        (id_employe,)
    ).fetchall()
    
    return render_template("bulletins/historique.html", employe=employe, bulletins=bulletins)

# routes/bulletin_routes.py - Version corrigée

def get_parametre(db, id_societe, code):
    """Récupère un paramètre (priorité à la société, puis global)"""
    result = db.execute(
        "SELECT valeur FROM parametre_legal WHERE (id_societe = ? OR id_societe IS NULL) AND code = ? ORDER BY id_societe DESC LIMIT 1",
        (id_societe, code)
    ).fetchone()
    return result["valeur"] if result else 0


# routes/bulletin_routes.py - Fonction pdf_bulletin corrigée

@bulletin_bp.route("/<int:id_bulletin>/pdf")
@role_requis("comptable", "admin_societe", "employe")
@societe_requise
def pdf_bulletin(id_bulletin):
    db = get_db()
    
    # Récupérer le bulletin
    bulletin = db.execute(
        "SELECT * FROM bulletin_paie WHERE id_bulletin = ?", (id_bulletin,)
    ).fetchone()
    
    if bulletin is None:
        flash("Bulletin introuvable.", "error")
        return redirect(url_for("employe.liste_employes"))
    
    # Récupérer l'employé
    employe = db.execute(
        """SELECT e.*, s.raison_sociale, s.adresse, s.ice, s.cnss, s.rc, s.mode_paiement 
           FROM employe e
           JOIN societe s ON s.id_societe = e.id_societe
           WHERE e.id_employe = ?""",
        (bulletin["id_employe"],)
    ).fetchone()
    
    if employe is None:
        flash("Employé introuvable.", "error")
        return redirect(url_for("employe.liste_employes"))
    
    # ==========================================
    # RÉCUPÉRER L'EMPLOYEUR (avec fallback)
    # ==========================================
    employeur = db.execute(
        "SELECT raison_sociale, adresse, ice, cnss, rc, mode_paiement, logo_path FROM societe WHERE id_societe = ?",
         (employe["id_societe"],)
    ).fetchone()
    
    # Si employeur est None, créer un dictionnaire par défaut
    if employeur is None:
        employeur = {
            "raison_sociale": "Société",
            "adresse": "Maroc",
            "ice": "",
            "cnss": "",
            "rc": "",
            "mode_paiement": "Virement bancaire / Chèque",
            "logo_path": ""
        }
    
    # Récupérer les lignes du bulletin
    lignes = db.execute(
        "SELECT * FROM ligne_bulletin WHERE id_bulletin = ? ORDER BY id_ligne",
        (id_bulletin,)
    ).fetchall()
    
    # ==========================================
    # RÉCUPÉRATION DES PARAMÈTRES DE LA BASE
    # ==========================================
    id_societe = employe["id_societe"]
    
    # Récupérer les taux depuis la base
    def get_parametre(db, id_societe, code):
        result = db.execute(
            "SELECT valeur FROM parametre_legal WHERE (id_societe = ? OR id_societe IS NULL) AND code = ? ORDER BY id_societe DESC LIMIT 1",
            (id_societe, code)
        ).fetchone()
        return result["valeur"] if result else 0
    
    taux_cnss = get_parametre(db, id_societe, "TAUX_CNSS") or 4.48
    taux_amo = get_parametre(db, id_societe, "TAUX_AMO") or 2.26
    taux_alloc_familiale = get_parametre(db, id_societe, "TAUX_ALLOC_FAMILIALE") or 6.40
    taux_prestations = get_parametre(db, id_societe, "TAUX_PRESTATIONS_SOCIALES") or 8.98
    taux_taxe_formation = get_parametre(db, id_societe, "TAUX_TAXE_FORMATION") or 1.60
    taux_amo_patronal = get_parametre(db, id_societe, "TAUX_AMO_PATRONAL") or 4.11
    taux_mutuelle = get_parametre(db, id_societe, "TAUX_MUTUELLE") or 2.59
    taux_cimr_salarial = get_parametre(db, id_societe, "TAUX_CIMR_SALARIAL") or 3.00
    taux_cimr_patronal = get_parametre(db, id_societe, "TAUX_CIMR_PATRONAL") or 3.90
    taux_perte_emploi = get_parametre(db, id_societe, "TAUX_PERTE_EMPLOI") or 0.19
    
    # ==========================================
    # VARIABLES POUR LE TEMPLATE
    # ==========================================
    
    from datetime import datetime
    
    # 1. Salaires
    salaire_base = bulletin["salaire_base"] if bulletin["salaire_base"] else employe["salaire_base"]
    salaire_brut = bulletin["salaire_brut"]
    salaire_net_imposable = bulletin["salaire_net_imposable"]
    salaire_net = bulletin["salaire_net_a_payer"]
    
    # 2. Cotisations
    cnss = bulletin["total_cnss"]
    amo = bulletin["total_amo"]
    ir = bulletin["total_ir"]
    
    # 3. Salaire journalier
    jours_travailles = employe["jours_travailles"] if employe["jours_travailles"] else 26
    salaire_journalier = salaire_base / jours_travailles if salaire_base else 0
    
    # 4. Ancienneté
    date_embauche = datetime.strptime(employe["date_embauche"], '%Y-%m-%d')
    aujourd_hui = datetime.now()
    anciennete = aujourd_hui.year - date_embauche.year
    if (aujourd_hui.month, aujourd_hui.day) < (date_embauche.month, date_embauche.day):
        anciennete -= 1
    anciennete = max(anciennete, 0)
    
    # 5. Taux d'ancienneté
    if anciennete >= 25:
        taux_anciennete = 25
    elif anciennete >= 20:
        taux_anciennete = 20
    elif anciennete >= 12:
        taux_anciennete = 15
    elif anciennete >= 5:
        taux_anciennete = 10
    elif anciennete >= 2:
        taux_anciennete = 5
    else:
        taux_anciennete = 0
    
    # 6. Prime d'ancienneté
    prime_anciennete = 0
    for ligne in lignes:
        if "ancienneté" in ligne["libelle"].lower():
            prime_anciennete = abs(ligne["montant"])
            break
    if prime_anciennete == 0:
        prime_anciennete = salaire_base * (taux_anciennete / 100) if taux_anciennete > 0 else 0
    
    # 7. Indemnités
    indemnites = []
    for ligne in lignes:
        libelle = ligne["libelle"].lower()
        if ligne["type_ligne"] == "gain" and "salaire de base" not in libelle and "ancienneté" not in libelle:
            indemnites.append({
                "libelle": ligne["libelle"],
                "montant": abs(ligne["montant"])
            })
    
    # 8. Total gains
    total_gains = sum([i["montant"] for i in indemnites]) + prime_anciennete
    
    # 9. Bases de calcul
    base_cnss = min(salaire_brut, 6000)
    base_amo = salaire_brut
    base_cimr = salaire_brut
    
    # 10. Cotisations salariales
    perte_emploi = base_cnss * (taux_perte_emploi / 100)
    mutuelle_salarial = base_amo * (taux_mutuelle / 100)
    cimr_salarial = base_cimr * (taux_cimr_salarial / 100)
    total_cotisations_salariales = cnss + amo + perte_emploi + mutuelle_salarial + cimr_salarial
    
    # 11. Cotisations patronales
    alloc_familiale_patronal = base_cnss * (taux_alloc_familiale / 100)
    prestations_sociales_patronal = base_cnss * (taux_prestations / 100)
    taxe_formation_patronal = base_cnss * (taux_taxe_formation / 100)
    amo_patronal = base_amo * (taux_amo_patronal / 100)
    mutuelle_patronal = base_amo * (taux_mutuelle / 100)
    cimr_patronal = base_cimr * (taux_cimr_patronal / 100)
    total_cotisations_patronales = (alloc_familiale_patronal + prestations_sociales_patronal + 
                                    taxe_formation_patronal + amo_patronal + mutuelle_patronal + cimr_patronal)
    
    # 12. Tranches IR
    tranches_ir = db.execute(
        "SELECT * FROM tranche_ir WHERE id_societe = ? OR id_societe IS NULL ORDER BY seuil_bas",
        (employe["id_societe"],)
    ).fetchall()
    
    # 13. Solde des congés
    solde = db.execute(
        """SELECT jours_restants FROM solde_conge 
           WHERE id_employe = ? AND annee = ? AND id_type_conge = 1""",
        (employe["id_employe"], datetime.now().year)
    ).fetchone()
    solde_conges = solde["jours_restants"] if solde else 0
    
    # 14. Situation familiale
    situation_familiale = employe["situation_familiale"] if employe["situation_familiale"] else "MARIE"
    cnss_numero = employe["cnss_numero"] if employe["cnss_numero"] else "-"
    
    # 15. Mode de paiement
    mode_paiement = employeur["mode_paiement"] if employeur and employeur["mode_paiement"] else "Virement bancaire / Chèque"
    
    # Créer l'objet bulletin avec toutes les données nécessaires
    bulletin_data = {
        "salaire_base": salaire_base,
        "salaire_brut": salaire_brut,
        "salaire_net_imposable": salaire_net_imposable,
        "salaire_net_a_payer": salaire_net,
        "total_cnss": cnss,
        "total_amo": amo,
        "total_ir": ir,
        "mois": bulletin["mois"],
        "annee": bulletin["annee"],
        "date_generation": bulletin["date_generation"]
    }
    
    # Vérification de cohérence
    total_retenues = total_cotisations_salariales + ir
    verification = {
        "brut": salaire_brut,
        "retenues": total_retenues,
        "net": salaire_net,
        "somme": round(salaire_net + total_retenues, 2),
        "est_coherent": round(salaire_net + total_retenues, 2) == round(salaire_brut, 2)
    }
    
    # Rendre le template
    html_content = render_template(
        "bulletins/bulletin_pdf_detaille.html",
        bulletin=bulletin_data,
        employe=employe,
        employeur=employeur,
        lignes=lignes,
        anciennete=anciennete,
        salaire_journalier=salaire_journalier,
        prime_anciennete=prime_anciennete,
        taux_anciennete=taux_anciennete,
        indemnites=indemnites,
        total_gains=total_gains,
        base_cnss=base_cnss,
        base_amo=base_amo,
        base_cimr=base_cimr,
        taux_cnss=taux_cnss,
        taux_amo=taux_amo,
        taux_mutuelle=taux_mutuelle,
        taux_cimr_salarial=taux_cimr_salarial,
        taux_cimr_patronal=taux_cimr_patronal,
        taux_alloc_familiale=taux_alloc_familiale,
        taux_prestations=taux_prestations,
        taux_taxe_formation=taux_taxe_formation,
        taux_amo_patronal=taux_amo_patronal,
        taux_perte_emploi=taux_perte_emploi,
        perte_emploi=perte_emploi,
        mutuelle_salarial=mutuelle_salarial,
        cimr_salarial=cimr_salarial,
        alloc_familiale_patronal=alloc_familiale_patronal,
        prestations_sociales_patronal=prestations_sociales_patronal,
        taxe_formation_patronal=taxe_formation_patronal,
        amo_patronal=amo_patronal,
        mutuelle_patronal=mutuelle_patronal,
        cimr_patronal=cimr_patronal,
        total_cotisations_salariales=total_cotisations_salariales,
        total_cotisations_patronales=total_cotisations_patronales,
        tranches_ir=tranches_ir,
        solde_conges=solde_conges,
        jours_travailles=jours_travailles,
        situation_familiale=situation_familiale,
        cnss_numero=cnss_numero,
        mode_paiement=mode_paiement,
        verification=verification,
        annee_courante=datetime.now().year,
        logo_path=employeur["logo_path"] if employeur else "",
    )
    
    # Générer le PDF
    try:
        config = get_pdfkit_config()
        if config:
            pdf_file = pdfkit.from_string(html_content, False, configuration=config)
        else:
            pdf_file = pdfkit.from_string(html_content, False)
        
        response = make_response(pdf_file)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=bulletin_{employe["matricule"]}_{bulletin["mois"]}_{bulletin["annee"]}.pdf'
        
        return response
    
    except Exception as e:
        flash(f"Erreur lors de la génération du PDF : {str(e)}", "danger")
        return redirect(url_for("bulletin.detail_bulletin", id_bulletin=id_bulletin))


# ============================================================
# EXPORT PDF - Mon bulletin (Employé)
# ============================================================
# routes/bulletin_routes.py

# routes/bulletin_routes.py - Fonction pdf_mon_bulletin corrigée

@bulletin_bp.route("/mon-bulletin/<int:id_bulletin>/pdf")
@role_requis("employe", "comptable", "rh")
def pdf_mon_bulletin(id_bulletin):
    db = get_db()
    
    # Récupérer l'employé connecté
    employe = db.execute(
        "SELECT * FROM employe WHERE id_utilisateur = ?",
        (session["id_utilisateur"],)
    ).fetchone()
    
    if employe is None:
        flash("Aucun profil employé associé à ce compte.", "error")
        return redirect(url_for("index"))
    
    # Vérifier que le bulletin appartient à l'employé
    bulletin = db.execute(
        "SELECT * FROM bulletin_paie WHERE id_bulletin = ? AND id_employe = ?",
        (id_bulletin, employe["id_employe"])
    ).fetchone()
    
    if bulletin is None:
        flash("Bulletin introuvable ou accès non autorisé.", "error")
        return redirect(url_for("bulletin.mon_bulletin"))
    
    # Récupérer les lignes
    lignes = db.execute(
        "SELECT * FROM ligne_bulletin WHERE id_bulletin = ? ORDER BY id_ligne",
        (id_bulletin,)
    ).fetchall()
    
    # Récupérer l'employeur
    employeur = db.execute(
        "SELECT raison_sociale, adresse, ice, cnss, rc FROM societe WHERE id_societe = ?",
        (employe["id_societe"],)
    ).fetchone()
    
    # Récupérer les paramètres
    id_societe = employe["id_societe"]
    
    def get_parametre(db, id_societe, code):
        result = db.execute(
            "SELECT valeur FROM parametre_legal WHERE (id_societe = ? OR id_societe IS NULL) AND code = ? ORDER BY id_societe DESC LIMIT 1",
            (id_societe, code)
        ).fetchone()
        return result["valeur"] if result else 0
    
    taux_cnss = get_parametre(db, id_societe, "TAUX_CNSS") or 4.48
    taux_amo = get_parametre(db, id_societe, "TAUX_AMO") or 2.26
    taux_alloc_familiale = get_parametre(db, id_societe, "TAUX_ALLOC_FAMILIALE") or 6.40
    taux_prestations = get_parametre(db, id_societe, "TAUX_PRESTATIONS_SOCIALES") or 8.98
    taux_taxe_formation = get_parametre(db, id_societe, "TAUX_TAXE_FORMATION") or 1.60
    taux_amo_patronal = get_parametre(db, id_societe, "TAUX_AMO_PATRONAL") or 4.11
    taux_mutuelle = get_parametre(db, id_societe, "TAUX_MUTUELLE") or 2.59
    taux_cimr_salarial = get_parametre(db, id_societe, "TAUX_CIMR_SALARIAL") or 3.00
    taux_cimr_patronal = get_parametre(db, id_societe, "TAUX_CIMR_PATRONAL") or 3.90
    taux_perte_emploi = get_parametre(db, id_societe, "TAUX_PERTE_EMPLOI") or 0.19
    
    from datetime import datetime
    
    # Salaires
    salaire_base = bulletin["salaire_base"] if bulletin["salaire_base"] else employe["salaire_base"]
    salaire_brut = bulletin["salaire_brut"]
    salaire_net_imposable = bulletin["salaire_net_imposable"]
    salaire_net = bulletin["salaire_net_a_payer"]
    
    # Cotisations
    cnss = bulletin["total_cnss"]
    amo = bulletin["total_amo"]
    ir = bulletin["total_ir"]
    
    # Salaire journalier
    jours_travailles = employe["jours_travailles"] if employe["jours_travailles"] else 26
    salaire_journalier = salaire_base / jours_travailles if salaire_base else 0
    
    # Ancienneté
    date_embauche = datetime.strptime(employe["date_embauche"], '%Y-%m-%d')
    aujourd_hui = datetime.now()
    anciennete = aujourd_hui.year - date_embauche.year
    if (aujourd_hui.month, aujourd_hui.day) < (date_embauche.month, date_embauche.day):
        anciennete -= 1
    anciennete = max(anciennete, 0)
    
    # Taux d'ancienneté
    if anciennete >= 25:
        taux_anciennete = 25
    elif anciennete >= 20:
        taux_anciennete = 20
    elif anciennete >= 12:
        taux_anciennete = 15
    elif anciennete >= 5:
        taux_anciennete = 10
    elif anciennete >= 2:
        taux_anciennete = 5
    else:
        taux_anciennete = 0
    
    # Prime d'ancienneté
    prime_anciennete = 0
    for ligne in lignes:
        if "ancienneté" in ligne["libelle"].lower():
            prime_anciennete = abs(ligne["montant"])
            break
    if prime_anciennete == 0:
        prime_anciennete = salaire_base * (taux_anciennete / 100) if taux_anciennete > 0 else 0
    
    # Indemnités
    indemnites = []
    for ligne in lignes:
        libelle = ligne["libelle"].lower()
        if ligne["type_ligne"] == "gain" and "salaire de base" not in libelle and "ancienneté" not in libelle:
            indemnites.append({
                "libelle": ligne["libelle"],
                "montant": abs(ligne["montant"])
            })
    
    total_gains = sum([i["montant"] for i in indemnites]) + prime_anciennete
    
    # Bases de calcul
    base_cnss = min(salaire_brut, 6000)
    base_amo = salaire_brut
    base_cimr = salaire_brut
    
    # Cotisations salariales
    perte_emploi = base_cnss * (taux_perte_emploi / 100)
    mutuelle_salarial = base_amo * (taux_mutuelle / 100)
    cimr_salarial = base_cimr * (taux_cimr_salarial / 100)
    total_cotisations_salariales = cnss + amo + perte_emploi + mutuelle_salarial + cimr_salarial
    
    # Cotisations patronales
    alloc_familiale_patronal = base_cnss * (taux_alloc_familiale / 100)
    prestations_sociales_patronal = base_cnss * (taux_prestations / 100)
    taxe_formation_patronal = base_cnss * (taux_taxe_formation / 100)
    amo_patronal = base_amo * (taux_amo_patronal / 100)
    mutuelle_patronal = base_amo * (taux_mutuelle / 100)
    cimr_patronal = base_cimr * (taux_cimr_patronal / 100)
    total_cotisations_patronales = (alloc_familiale_patronal + prestations_sociales_patronal + 
                                    taxe_formation_patronal + amo_patronal + mutuelle_patronal + cimr_patronal)
    
    # Tranches IR
    tranches_ir = db.execute(
        "SELECT * FROM tranche_ir WHERE id_societe = ? OR id_societe IS NULL ORDER BY seuil_bas",
        (employe["id_societe"],)
    ).fetchall()
    
    # Solde des congés
    solde = db.execute(
        """SELECT jours_restants FROM solde_conge 
           WHERE id_employe = ? AND annee = ? AND id_type_conge = 1""",
        (employe["id_employe"], datetime.now().year)
    ).fetchone()
    solde_conges = solde["jours_restants"] if solde else 0
    
    # Situation familiale
    situation_familiale = employe["situation_familiale"] if employe["situation_familiale"] else "MARIE"
    cnss_numero = employe["cnss_numero"] if employe["cnss_numero"] else "-"
    
    # Créer l'objet bulletin
    bulletin_data = {
        "salaire_base": salaire_base,
        "salaire_brut": salaire_brut,
        "salaire_net_imposable": salaire_net_imposable,
        "salaire_net_a_payer": salaire_net,
        "total_cnss": cnss,
        "total_amo": amo,
        "total_ir": ir,
        "mois": bulletin["mois"],
        "annee": bulletin["annee"],
        "date_generation": bulletin["date_generation"]
    }
    
    # Rendre le template
    html_content = render_template(
        "bulletins/bulletin_pdf_detaille.html",
        bulletin=bulletin_data,
        employe=employe,
        employeur=employeur,
        lignes=lignes,
        anciennete=anciennete,
        salaire_journalier=salaire_journalier,
        prime_anciennete=prime_anciennete,
        taux_anciennete=taux_anciennete,
        indemnites=indemnites,
        total_gains=total_gains,
        base_cnss=base_cnss,
        base_amo=base_amo,
        base_cimr=base_cimr,
        taux_cnss=taux_cnss,
        taux_amo=taux_amo,
        taux_mutuelle=taux_mutuelle,
        taux_cimr_salarial=taux_cimr_salarial,
        taux_cimr_patronal=taux_cimr_patronal,
        taux_alloc_familiale=taux_alloc_familiale,
        taux_prestations=taux_prestations,
        taux_taxe_formation=taux_taxe_formation,
        taux_amo_patronal=taux_amo_patronal,
        taux_perte_emploi=taux_perte_emploi,
        perte_emploi=perte_emploi,
        mutuelle_salarial=mutuelle_salarial,
        cimr_salarial=cimr_salarial,
        alloc_familiale_patronal=alloc_familiale_patronal,
        prestations_sociales_patronal=prestations_sociales_patronal,
        taxe_formation_patronal=taxe_formation_patronal,
        amo_patronal=amo_patronal,
        mutuelle_patronal=mutuelle_patronal,
        cimr_patronal=cimr_patronal,
        total_cotisations_salariales=total_cotisations_salariales,
        total_cotisations_patronales=total_cotisations_patronales,
        tranches_ir=tranches_ir,
        solde_conges=solde_conges,
        jours_travailles=jours_travailles,
        situation_familiale=situation_familiale,
        cnss_numero=cnss_numero,
        annee_courante=datetime.now().year
    )
    
    # Générer le PDF
    try:
        config = get_pdfkit_config()
        if config:
            pdf_file = pdfkit.from_string(html_content, False, configuration=config)
        else:
            pdf_file = pdfkit.from_string(html_content, False)
        
        response = make_response(pdf_file)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=bulletin_{employe["matricule"]}_{bulletin["mois"]}_{bulletin["annee"]}.pdf'
        
        return response
    
    except Exception as e:
        flash(f"Erreur lors de la génération du PDF : {str(e)}", "danger")
        return redirect(url_for("bulletin.mon_bulletin_detail", id_bulletin=id_bulletin))
    

# routes/bulletin_routes.py - Ajouter

@bulletin_bp.route("/statistiques")
@role_requis("comptable")
@societe_requise
def statistiques_bulletins():
    db = get_db()
    id_societe = session.get("id_societe")
    
    # Statistiques globales
    total_bulletins = db.execute(
        """SELECT COUNT(*) AS n FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ?""",
        (id_societe,)
    ).fetchone()["n"]
    
    # Masse salariale totale
    masse_totale = db.execute(
        """SELECT COALESCE(SUM(bp.salaire_net_a_payer), 0) AS total FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ?""",
        (id_societe,)
    ).fetchone()["total"]
    
    # Bulletins du mois en cours
    from datetime import datetime
    mois_courant = datetime.now().month
    annee_courante = datetime.now().year
    
    bulletins_mois = db.execute(
        """SELECT COUNT(*) AS n FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ? AND bp.mois = ? AND bp.annee = ?""",
        (id_societe, mois_courant, annee_courante)
    ).fetchone()["n"]
    
    # Employés sans bulletin ce mois
    employes_sans_bulletin = db.execute(
        """SELECT COUNT(*) AS n FROM employe e
           WHERE e.id_societe = ? AND e.actif = 1
           AND NOT EXISTS (
               SELECT 1 FROM bulletin_paie bp 
               WHERE bp.id_employe = e.id_employe 
               AND bp.mois = ? AND bp.annee = ?
           )""",
        (id_societe, mois_courant, annee_courante)
    ).fetchone()["n"]
    
    # Derniers bulletins générés
    derniers_bulletins = db.execute(
        """SELECT bp.*, e.nom, e.prenom, e.matricule
           FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           WHERE e.id_societe = ?
           ORDER BY bp.date_generation DESC
           LIMIT 5""",
        (id_societe,)
    ).fetchall()
    
    return render_template(
        "comptable/statistiques.html",
        total_bulletins=total_bulletins,
        masse_totale=masse_totale,
        bulletins_mois=bulletins_mois,
        employes_sans_bulletin=employes_sans_bulletin,
        derniers_bulletins=derniers_bulletins,
        mois_courant=mois_courant,
        annee_courante=annee_courante
    )

@bulletin_bp.route("/export")
@role_requis("admin_societe", "comptable")
@societe_requise
def export_bulletins_csv():
    """Exporter la liste des bulletins en CSV/Excel"""
    db = get_db()
    id_societe = session.get("id_societe")
    
    # Récupérer les bulletins
    bulletins = db.execute(
        """SELECT bp.*, e.nom, e.prenom, e.matricule, s.raison_sociale
           FROM bulletin_paie bp
           JOIN employe e ON e.id_employe = bp.id_employe
           JOIN societe s ON s.id_societe = e.id_societe
           WHERE e.id_societe = ?
           ORDER BY bp.annee DESC, bp.mois DESC""",
        (id_societe,)
    ).fetchall()
    
    # Préparer les données
    headers, data = export_bulletins(bulletins)
    
    # Choisir le format
    format_type = request.args.get('format', 'csv')
    
    if format_type == 'excel':
        return export_to_excel(data, headers, 'bulletins')
    else:
        return export_to_csv(data, headers, 'bulletins')

