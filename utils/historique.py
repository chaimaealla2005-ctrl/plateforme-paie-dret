# utils/historique.py
from db import get_db
import json


def enregistrer_modification(id_utilisateur, id_societe, categorie, 
                             id_element, code_element, champ_modifie, 
                             ancienne_valeur, nouvelle_valeur):
    """
    Enregistre une modification de paramètre dans l'historique
    """
    try:
        db = get_db()
        db.execute(
            """INSERT INTO historique_parametres 
               (id_utilisateur, id_societe, categorie, id_element, code_element, 
                champ_modifie, ancienne_valeur, nouvelle_valeur)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (id_utilisateur, id_societe, categorie, id_element, code_element,
             champ_modifie, str(ancienne_valeur), str(nouvelle_valeur))
        )
        db.commit()
        return True
    except Exception as e:
        print(f"❌ Erreur enregistrement historique: {e}")
        return False


def enregistrer_modification_multi(id_utilisateur, id_societe, categorie,
                                   id_element, code_element, modifications):
    """
    Enregistre plusieurs modifications d'un même élément
    modifications: dict {champ: (ancienne_valeur, nouvelle_valeur)}
    """
    db = get_db()
    for champ, (ancienne, nouvelle) in modifications.items():
        if ancienne != nouvelle:
            db.execute(
                """INSERT INTO historique_parametres 
                   (id_utilisateur, id_societe, categorie, id_element, code_element, 
                    champ_modifie, ancienne_valeur, nouvelle_valeur)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (id_utilisateur, id_societe, categorie, id_element, code_element,
                 champ, str(ancienne) if ancienne is not None else 'NULL', 
                 str(nouvelle) if nouvelle is not None else 'NULL')
            )
    db.commit()


def get_historique_parametres(filtre_categorie=None, filtre_utilisateur=None, 
                              limit=100, offset=0):
    """
    Récupère l'historique des modifications
    """
    db = get_db()
    query = """
        SELECT h.*, u.nom, u.prenom, u.email,
               s.raison_sociale as societe_nom
        FROM historique_parametres h
        LEFT JOIN utilisateur u ON u.id_utilisateur = h.id_utilisateur
        LEFT JOIN societe s ON s.id_societe = h.id_societe
        WHERE 1=1
    """
    params = []
    
    if filtre_categorie:
        query += " AND h.categorie = ?"
        params.append(filtre_categorie)
    
    if filtre_utilisateur:
        query += " AND h.id_utilisateur = ?"
        params.append(filtre_utilisateur)
    
    query += " ORDER BY h.date_modification DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    return db.execute(query, params).fetchall()


def get_historique_by_element(categorie, id_element, limit=50):
    """
    Récupère l'historique pour un élément spécifique
    """
    db = get_db()
    return db.execute(
        """SELECT h.*, u.nom, u.prenom, u.email
           FROM historique_parametres h
           LEFT JOIN utilisateur u ON u.id_utilisateur = h.id_utilisateur
           WHERE h.categorie = ? AND h.id_element = ?
           ORDER BY h.date_modification DESC
           LIMIT ?""",
        (categorie, id_element, limit)
    ).fetchall()