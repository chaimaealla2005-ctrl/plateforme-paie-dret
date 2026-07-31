# routes/conge_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory
from db import get_db
import db
from utils.decorators import role_requis, societe_requise
from utils.journal import enregistrer_action
from datetime import datetime, timedelta
import os
import calendar
from werkzeug.utils import secure_filename
from utils.email import notifier_employe_conge, notifier_rh_nouvelle_demande


conge_bp = Blueprint("conge", __name__, url_prefix="/conges")

# Configuration pour l'upload de fichiers
UPLOAD_FOLDER = 'uploads/conges'
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 Mo

# Créer le dossier d'upload si nécessaire
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# CALCUL DES JOURS OUVRES
# ============================================================
def calculer_jours_ouvres(date_debut, date_fin):
    """Calcule le nombre de jours ouvrés entre deux dates (lundi-vendredi)"""
    debut = datetime.strptime(date_debut, '%Y-%m-%d')
    fin = datetime.strptime(date_fin, '%Y-%m-%d')
    
    jours_ouvres = 0
    current = debut
    while current <= fin:
        if current.weekday() < 5:  # 0=lundi, 4=vendredi
            jours_ouvres += 1
        current += timedelta(days=1)
    
    return jours_ouvres


# ============================================================
# CALCUL DE L'ANCIENNETE
# ============================================================
def calculer_anciennete(date_embauche_str):
    """Calcule le nombre d'années d'ancienneté"""
    date_embauche = datetime.strptime(date_embauche_str, '%Y-%m-%d')
    aujourd_hui = datetime.now()
    annees = aujourd_hui.year - date_embauche.year
    if (aujourd_hui.month, aujourd_hui.day) < (date_embauche.month, date_embauche.day):
        annees -= 1
    return max(annees, 0)


# ============================================================
# INDEX - MES CONGES (Employé)
# ============================================================
@conge_bp.route("/")
@conge_bp.route("/mes-conges")
@role_requis("employe", "rh", "comptable", "admin_societe")
def mes_conges():
    db = get_db()
    
    # Récupérer l'employé connecté
    employe = db.execute(
        "SELECT * FROM employe WHERE id_utilisateur = ?",
        (session["id_utilisateur"],)
    ).fetchone()

    # Si l'utilisateur n'a pas de fiche employé, lui en créer une automatiquement
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
            flash("✅ Une fiche employé a été automatiquement créée pour votre compte.", "success")
    
    if employe is None:
        flash("Aucun profil employé associé à ce compte. Veuillez contacter l'administrateur.", "error")
        return redirect(url_for("index"))
    
    if employe is None:
        flash("Aucun profil employé associé à ce compte.", "error")
        return redirect(url_for("index"))
    
    id_employe = employe["id_employe"]
    annee_courante = datetime.now().year
    
    # Récupérer les soldes de congés
    soldes = db.execute(
        """SELECT sc.*, tc.code, tc.libelle, tc.jours_par_an
           FROM solde_conge sc
           JOIN type_conge tc ON tc.id_type_conge = sc.id_type_conge
           WHERE sc.id_employe = ? AND sc.annee = ?
           ORDER BY tc.code""",
        (id_employe, annee_courante)
    ).fetchall()
    
    # Si pas de soldes pour l'année, les créer
    if not soldes:
        types_conges = db.execute(
            "SELECT * FROM type_conge WHERE actif = 1"
        ).fetchall()
        
        for tc in types_conges:
            jours_acquis = tc["jours_par_an"]
            
            # Pour les congés payés, ajouter des jours selon l'ancienneté
            if tc["code"] == "CP":
                anciennete = calculer_anciennete(employe["date_embauche"])
                if anciennete >= 10:
                    jours_acquis += 5
                elif anciennete >= 5:
                    jours_acquis += 3
            
            db.execute(
                """INSERT INTO solde_conge (id_employe, id_type_conge, annee, jours_acquis, jours_pris, jours_restants)
                   VALUES (?, ?, ?, ?, 0, ?)""",
                (id_employe, tc["id_type_conge"], annee_courante, jours_acquis, jours_acquis)
            )
        
        db.commit()
        
        # Recharger les soldes
        soldes = db.execute(
            """SELECT sc.*, tc.code, tc.libelle, tc.jours_par_an
               FROM solde_conge sc
               JOIN type_conge tc ON tc.id_type_conge = sc.id_type_conge
               WHERE sc.id_employe = ? AND sc.annee = ?
               ORDER BY tc.code""",
            (id_employe, annee_courante)
        ).fetchall()
    
    # Récupérer les demandes de congé
    demandes = db.execute(
        """SELECT c.*, tc.code, tc.libelle
           FROM conge c
           JOIN type_conge tc ON tc.id_type_conge = c.id_type_conge
           WHERE c.id_employe = ?
           ORDER BY c.date_demande DESC""",
        (id_employe,)
    ).fetchall()
    
    return render_template(
        "conges/mes_conges.html",
        employe=employe,
        soldes=soldes,
        demandes=demandes,
        annee_courante=annee_courante
    )


# ============================================================
# DEMANDER UN CONGE (AVEC PIECE JOINTE)
# ============================================================
@conge_bp.route("/demander", methods=["GET", "POST"])
@role_requis("employe", "comptable", "rh", "admin_societe")
def demander_conge():
    db = get_db()
    
    # Récupérer l'employé connecté
    employe = db.execute(
        "SELECT * FROM employe WHERE id_utilisateur = ?",
        (session["id_utilisateur"],)
    ).fetchone()
    
    if employe is None:
        flash("Aucun profil employé associé à ce compte.", "error")
        return redirect(url_for("index"))
    
    # Récupérer les types de congés disponibles avec le solde restant
    types_conges = db.execute(
        """SELECT tc.*, 
                  COALESCE(sc.jours_restants, 0) as solde_restant,
                  COALESCE(sc.jours_acquis, 0) as solde_acquis,
                  COALESCE(sc.jours_pris, 0) as solde_pris
           FROM type_conge tc
           LEFT JOIN solde_conge sc ON sc.id_type_conge = tc.id_type_conge 
               AND sc.id_employe = ? AND sc.annee = ?
           WHERE tc.actif = 1
           ORDER BY tc.code""",
        (employe["id_employe"], datetime.now().year)
    ).fetchall()
    
    if request.method == "POST":
        id_type_conge = request.form.get("id_type_conge")
        date_debut = request.form.get("date_debut")
        date_fin = request.form.get("date_fin")
        motif = request.form.get("motif", "")
        
        # Vérifications de base
        if not id_type_conge or not date_debut or not date_fin:
            flash("Tous les champs sont obligatoires.", "error")
            return redirect(url_for("conge.demander_conge"))
        
        # Vérifier les dates
        aujourd_hui = datetime.now().date()
        date_debut_obj = datetime.strptime(date_debut, '%Y-%m-%d').date()
        if date_debut_obj < aujourd_hui:
            flash("La date de début doit être à partir d'aujourd'hui.", "error")
            return redirect(url_for("conge.demander_conge"))
        
        date_fin_obj = datetime.strptime(date_fin, '%Y-%m-%d').date()
        if date_fin_obj < date_debut_obj:
            flash("La date de fin doit être après la date de début.", "error")
            return redirect(url_for("conge.demander_conge"))
        
        # Calculer le nombre de jours ouvrés
        nb_jours = calculer_jours_ouvres(date_debut, date_fin)
        
        if nb_jours == 0:
            flash("La période demandée ne contient pas de jours ouvrés.", "error")
            return redirect(url_for("conge.demander_conge"))
        
        # Récupérer le type de congé
        type_conge = db.execute(
            "SELECT * FROM type_conge WHERE id_type_conge = ?",
            (id_type_conge,)
        ).fetchone()
        
        if type_conge is None:
            flash("Type de congé invalide.", "error")
            return redirect(url_for("conge.demander_conge"))
        
        # ============================================================
        # GESTION DE LA PIECE JOINTE (Factorisée)
        # ============================================================
        piece_jointe = None
        
        # Types de congés nécessitant une pièce jointe
        types_avec_piece = ["MALADIE", "EXCEPTIONNEL"]
        
        if type_conge["code"] in types_avec_piece:
            if 'piece_jointe' not in request.files:
                flash("Une pièce justificative est obligatoire pour ce type de congé.", "error")
                return redirect(url_for("conge.demander_conge"))
            
            file = request.files['piece_jointe']
            
            if file.filename == '':
                flash("Veuillez sélectionner un fichier.", "error")
                return redirect(url_for("conge.demander_conge"))
            
            if file and allowed_file(file.filename):
                # Vérifier la taille du fichier
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    flash("Le fichier est trop volumineux (max 5 Mo).", "error")
                    return redirect(url_for("conge.demander_conge"))
                
                # Générer un nom de fichier unique
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{employe['matricule']}_{filename}"
                
                # Sauvegarder le fichier
                filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                file.save(filepath)
                
                piece_jointe = unique_filename
                
                if type_conge["code"] == "MALADIE":
                    flash("Certificat médical téléchargé avec succès.", "success")
                else:
                    flash("Pièce justificative téléchargée avec succès.", "success")
            else:
                flash("Format de fichier non accepté. Utilisez PDF, JPG, PNG ou GIF.", "error")
                return redirect(url_for("conge.demander_conge"))
        
        # ============================================================
        # LOGIQUE DE GESTION DES SOLDES (AMELIOREE)
        # ============================================================
        
        # Types de congés avec solde limité
        types_avec_solde = ["CP", "CPS"]
        
        if type_conge["code"] in types_avec_solde:
            solde = db.execute(
                "SELECT jours_restants FROM solde_conge WHERE id_employe = ? AND id_type_conge = ? AND annee = ?",
                (employe["id_employe"], id_type_conge, datetime.now().year)
            ).fetchone()
            
            jours_disponibles = solde["jours_restants"] if solde else 0
            
            # Vérification stricte - empêcher si solde insuffisant
            if jours_disponibles < nb_jours:
                flash(f"❌ Solde insuffisant pour {type_conge['libelle']}. Il vous reste {jours_disponibles} jours. Vous avez demandé {nb_jours} jours.", "error")
                return redirect(url_for("conge.demander_conge"))
            
            # Alerte si solde faible (moins de 5 jours restants)
            if jours_disponibles - nb_jours < 5:
                flash(f"⚠️ Attention : Après cette demande, il vous restera {jours_disponibles - nb_jours} jours de {type_conge['libelle']}.", "warning")
        
        # 2. Congé maladie - Vérifier que le fichier est présent
        elif type_conge["code"] == "MALADIE":
            if not piece_jointe:
                flash("Un certificat médical est obligatoire pour les congés maladie.", "error")
                return redirect(url_for("conge.demander_conge"))
        
        # 3. Congé exceptionnel - Vérifier le motif
        elif type_conge["code"] == "EXCEPTIONNEL":
            if not piece_jointe:
                flash("Une pièce justificative est obligatoire pour les congés exceptionnels.", "error")
                return redirect(url_for("conge.demander_conge"))
            
            motifs_valides = ["mariage", "naissance", "décès", "deces", "demenagement", "mutation"]
            if not any(m in motif.lower() for m in motifs_valides):
                flash("⚠️ Veuillez préciser le motif de votre congé exceptionnel (mariage, naissance, décès, déménagement, mutation).", "warning")
        
        # 4. Congé sans solde - Pas de vérification
        elif type_conge["code"] == "SANS_SOLDE":
            pass
        
        # Créer la demande de congé avec la pièce jointe
        db.execute(
            """INSERT INTO conge (id_employe, id_type_conge, date_debut, date_fin, nb_jours_ouvres, statut, motif, piece_jointe)
               VALUES (?, ?, ?, ?, ?, 'en_attente', ?, ?)""",
            (employe["id_employe"], id_type_conge, date_debut, date_fin, nb_jours, motif, piece_jointe)
        )
        db.commit()
        
        enregistrer_action(db, "demande_conge", f"Demande de congé pour {employe['nom']} {employe['prenom']}")

        # ============================================================
        # NOTIFICATION RH
        # ============================================================
        rh_emails = db.execute(
            "SELECT email FROM utilisateur WHERE id_societe = ? AND role = 'rh' AND actif = 1",
            (employe["id_societe"],)
        ).fetchall()
    
        if rh_emails:
            rh_email_list = [r["email"] for r in rh_emails]
            notifier_rh_nouvelle_demande(
                rh_email_list,
                f"{employe['prenom']} {employe['nom']}",
                type_conge["libelle"],
                date_debut,
                date_fin
            )
    
        flash("Votre demande de congé a été envoyée avec succès.", "success")
        return redirect(url_for("conge.mes_conges"))

    return render_template(
        "conges/demander.html",
        employe=employe,
        types_conges=types_conges,
        today=datetime.now().strftime('%Y-%m-%d')
    )

# ============================================================
# ANNULER UNE DEMANDE DE CONGE (EMPLOYE)
# ============================================================
@conge_bp.route("/annuler/<int:id_conge>", methods=["POST"])
@role_requis("employe", "rh", "comptable", "admin_societe")
def annuler_conge(id_conge):
    db = get_db()
    
    # Vérifier que la demande appartient à l'employé et est en attente
    conge = db.execute(
        """SELECT c.*, e.id_utilisateur 
           FROM conge c
           JOIN employe e ON e.id_employe = c.id_employe
           WHERE c.id_conge = ? AND c.statut = 'en_attente'""",
        (id_conge,)
    ).fetchone()
    
    if conge is None:
        flash("Demande introuvable ou déjà traitée.", "error")
        return redirect(url_for("conge.mes_conges"))
    
    if conge["id_utilisateur"] != session["id_utilisateur"]:
        flash("Vous ne pouvez pas annuler cette demande.", "error")
        return redirect(url_for("conge.mes_conges"))
    
    db.execute(
        "UPDATE conge SET statut = 'annule' WHERE id_conge = ?",
        (id_conge,)
    )
    db.commit()
    
    enregistrer_action(db, "annulation_conge", f"Demande de congé annulée (id={id_conge})")
    flash("Votre demande de congé a été annulée.", "success")
    return redirect(url_for("conge.mes_conges"))


# ============================================================
# GERER LES CONGES (RH / Admin Société)
# ============================================================
# routes/conge_routes.py - Vérifier la fonction gerer_conges

@conge_bp.route("/gerer")
@role_requis("rh", "admin_societe")
@societe_requise
def gerer_conges():
    db = get_db()
    id_societe = session.get("id_societe")
    
    # Récupérer les demandes en attente avec piece_jointe
    demandes_attente = db.execute(
        """SELECT c.*, e.nom, e.prenom, e.matricule, tc.libelle as type_libelle
           FROM conge c
           JOIN employe e ON e.id_employe = c.id_employe
           JOIN type_conge tc ON tc.id_type_conge = c.id_type_conge
           WHERE e.id_societe = ? AND c.statut = 'en_attente'
           ORDER BY c.date_demande ASC""",
        (id_societe,)
    ).fetchall()
    
    # Récupérer toutes les demandes avec piece_jointe
    toutes_demandes = db.execute(
        """SELECT c.*, e.nom, e.prenom, e.matricule, tc.libelle as type_libelle
           FROM conge c
           JOIN employe e ON e.id_employe = c.id_employe
           JOIN type_conge tc ON tc.id_type_conge = c.id_type_conge
           WHERE e.id_societe = ?
           ORDER BY c.date_demande DESC
           LIMIT 100""",
        (id_societe,)
    ).fetchall()
    
    return render_template(
        "conges/gerer.html",
        demandes_attente=demandes_attente,
        toutes_demandes=toutes_demandes
    )


# ============================================================
# REPONDRE A UNE DEMANDE DE CONGE (RH / Admin Société)
# ============================================================
@conge_bp.route("/repondre/<int:id_conge>", methods=["POST"])
@role_requis("rh", "admin_societe")
@societe_requise
def repondre_conge(id_conge):
    db = get_db()
    id_societe = session.get("id_societe")
    
    # Vérifier que la demande existe et est en attente
    conge = db.execute(
        """SELECT c.*, e.id_societe, e.email, e.nom, e.prenom, tc.libelle as type_libelle, tc.code as type_code
           FROM conge c
           JOIN employe e ON e.id_employe = c.id_employe
           JOIN type_conge tc ON tc.id_type_conge = c.id_type_conge
           WHERE c.id_conge = ? AND c.statut = 'en_attente'""",
        (id_conge,)
    ).fetchone()
    
    if conge is None:
        flash("Demande introuvable ou déjà traitée.", "error")
        return redirect(url_for("conge.gerer_conges"))
    
    if conge["id_societe"] != id_societe:
        flash("Vous ne pouvez pas traiter cette demande.", "error")
        return redirect(url_for("conge.gerer_conges"))
    
    action = request.form.get("action")
    commentaire = request.form.get("commentaire", "")
    
    if action not in ["approuver", "refuser"]:
        flash("Action invalide.", "error")
        return redirect(url_for("conge.gerer_conges"))
    
    nouveau_statut = "approuve" if action == "approuver" else "refuse"
    
    # ============================================================
    # VERIFICATION DU SOLDE AVANT APPROBATION
    # ============================================================
    # Types de congés avec solde limité
    types_avec_solde = ["CP", "CPS"]
    
    if action == "approuver" and conge["type_code"] in types_avec_solde:
        solde_actuel = db.execute(
            "SELECT jours_restants FROM solde_conge WHERE id_employe = ? AND id_type_conge = ? AND annee = ?",
            (conge["id_employe"], conge["id_type_conge"], datetime.now().year)
        ).fetchone()
        
        jours_disponibles = solde_actuel["jours_restants"] if solde_actuel else 0
        
        # Vérification stricte - ne pas approuver si solde insuffisant
        if jours_disponibles < conge["nb_jours_ouvres"]:
            flash(f"❌ Solde insuffisant pour approuver cette demande de {conge['type_libelle']}. Solde restant : {jours_disponibles} jours.", "error")
            return redirect(url_for("conge.gerer_conges"))
    
    # Mettre à jour la demande
    db.execute(
        """UPDATE conge 
           SET statut = ?, date_reponse = datetime('now'), id_utilisateur_reponse = ?, commentaire_reponse = ?
           WHERE id_conge = ?""",
        (nouveau_statut, session["id_utilisateur"], commentaire, id_conge)
    )
    
    # Si approuvé, mettre à jour le solde de congés (uniquement pour CP et CPS)
    if action == "approuver" and conge["type_code"] in types_avec_solde:
        db.execute(
            """UPDATE solde_conge 
               SET jours_pris = jours_pris + ?, jours_restants = jours_restants - ?
               WHERE id_employe = ? AND id_type_conge = ? AND annee = ?""",
            (conge["nb_jours_ouvres"], conge["nb_jours_ouvres"], 
             conge["id_employe"], conge["id_type_conge"], datetime.now().year)
        )
    
    db.commit()
    
    # ============================================================
    # NOTIFICATION EMPLOYE
    # ============================================================
    if conge["email"]:
        notifier_employe_conge(
            conge["email"],
            f"{conge['prenom']} {conge['nom']}",
            conge["type_libelle"],
            conge["date_debut"],
            conge["date_fin"],
            nouveau_statut,
            commentaire
        )
    
    action_texte = "approuvée" if action == "approuver" else "refusée"
    enregistrer_action(db, "reponse_conge", f"Demande de congé {action_texte} (id={id_conge})")
    flash(f"Demande de congé {action_texte} avec succès.", "success")
    
    return redirect(url_for("conge.gerer_conges"))


# ============================================================
# TELECHARGER LA PIECE JOINTE (RH / Admin Société)
# ============================================================
@conge_bp.route("/piece-jointe/<filename>")
@role_requis("rh", "admin_societe")
@societe_requise
def telecharger_piece_jointe(filename):
    """Télécharger la pièce jointe d'une demande de congé"""
    # Vérifier que le fichier existe
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        flash("Fichier introuvable.", "error")
        return redirect(url_for("conge.gerer_conges"))
    
    return send_from_directory(UPLOAD_FOLDER, filename)