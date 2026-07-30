# routes/historique_routes.py
from flask import Blueprint, render_template, request, session
from db import get_db
from utils.decorators import role_requis
from utils.historique import get_historique_parametres
import math

historique_bp = Blueprint("historique", __name__, url_prefix="/historique")


@historique_bp.route("/parametres")
@role_requis("super_admin")
def historique_parametres():
    db = get_db()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    if per_page > 100:
        per_page = 100
    
    # Récupérer les filtres
    filtre_categorie = request.args.get('categorie', '')
    filtre_utilisateur = request.args.get('utilisateur', '')
    
    # Récupérer les historiques
    offset = (page - 1) * per_page
    historiques = get_historique_parametres(
        filtre_categorie if filtre_categorie else None,
        int(filtre_utilisateur) if filtre_utilisateur else None,
        per_page, offset
    )
    
    # Compter le total
    query = "SELECT COUNT(*) AS total FROM historique_parametres WHERE 1=1"
    params = []
    if filtre_categorie:
        query += " AND categorie = ?"
        params.append(filtre_categorie)
    if filtre_utilisateur:
        query += " AND id_utilisateur = ?"
        params.append(int(filtre_utilisateur))
    
    total = db.execute(query, params).fetchone()["total"]
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    
    # Récupérer les utilisateurs pour le filtre
    utilisateurs = db.execute(
        "SELECT id_utilisateur, nom, prenom, email FROM utilisateur ORDER BY nom"
    ).fetchall()
    
    # Catégories pour le filtre
    categories = db.execute(
        "SELECT DISTINCT categorie FROM historique_parametres ORDER BY categorie"
    ).fetchall()
    
    return render_template(
        "historique/parametres.html",
        historiques=historiques,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        utilisateurs=utilisateurs,
        categories=categories,
        filtre_categorie=filtre_categorie,
        filtre_utilisateur=filtre_utilisateur
    )