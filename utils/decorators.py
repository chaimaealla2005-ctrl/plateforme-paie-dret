# utils/decorators.py
from functools import wraps
from flask import session, redirect, url_for, abort, flash


def role_requis(*roles_autorises):
    """
    Usage :
        @role_requis('admin_societe', 'rh')
        def ma_route():
            ...

    Verifie dans l'ordre :
      1. Que l'utilisateur est connecte (sinon -> page de connexion)
      2. Que son role fait partie de ceux autorises (sinon -> erreur 403)
    """
    def decorateur(fonction_route):
        @wraps(fonction_route)
        def wrapper(*args, **kwargs):
            if "id_utilisateur" not in session:
                flash("Veuillez vous connecter pour accéder à cette page.", "error")
                return redirect(url_for("auth.login"))

            if session.get("role") not in roles_autorises:
                abort(403)  # Acces interdit

            return fonction_route(*args, **kwargs)
        return wrapper
    return decorateur


def societe_requise(f):
    """
    Decorateur pour s'assurer que l'utilisateur est rattache a une societe.
    Usage :
        @societe_requise
        def ma_route():
            ...

    Verifie que l'utilisateur a bien un id_societe (sauf pour super_admin).
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "id_utilisateur" not in session:
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("auth.login"))
        
        # Si l'utilisateur est super_admin, il n'est pas rattache a une societe
        if session.get("role") == "super_admin":
            return f(*args, **kwargs)
        
        # Pour les autres roles, id_societe doit etre present
        if session.get("id_societe") is None:
            flash("Vous devez etre rattache a une societe.", "danger")
            return redirect(url_for("index"))
        
        return f(*args, **kwargs)
    return wrapper


def verifier_societe(f):
    """
    Decorateur pour verifier que l'utilisateur a acces a la societe demandee.
    Usage :
        @verifier_societe
        def ma_route(id_societe):
            ...
    
    Verifie que l'id_societe de la route correspond a l'id_societe de l'utilisateur
    (sauf pour super_admin qui a acces a tout).
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "id_utilisateur" not in session:
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("auth.login"))
        
        # Super_admin peut tout voir
        if session.get("role") == "super_admin":
            return f(*args, **kwargs)
        
        # Pour les autres roles, on verifie l'id_societe
        id_societe_demande = kwargs.get("id_societe")
        if id_societe_demande and session.get("id_societe") != id_societe_demande:
            abort(403)  # Acces interdit
        
        return f(*args, **kwargs)
    return wrapper