# utils/email.py
from flask import current_app
from flask_mail import Message
from db import get_db
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _get_parametres_email():
    """Récupère les paramètres SMTP depuis la base de données"""
    try:
        db = get_db()
        params = db.execute("SELECT code, valeur FROM parametre_notification").fetchall()
        return {p["code"]: p["valeur"] for p in params}
    except Exception as e:
        print(f"⚠️ Erreur lors de la récupération des paramètres: {e}")
        return {}


def send_email(to, subject, body, html=None):
    """Envoie un email avec les paramètres stockés en base"""
    params = _get_parametres_email()
    
    # Afficher les paramètres pour debug
    print("📧 [DEBUG] Paramètres récupérés:")
    for key, value in params.items():
        if key == 'SMTP_MOT_DE_PASSE':
            print(f"   {key}: {'*' * len(value) if value else 'vide'}")
        else:
            print(f"   {key}: {value}")
    
    # Vérifier si les notifications sont activées
    if params.get('ACTIVER_NOTIFICATIONS', '0') != '1':
        print("📧 [NOTIFICATIONS DESACTIVEES] Activer_notifications =", params.get('ACTIVER_NOTIFICATIONS'))
        print("=" * 60)
        print(f"📧 [EMAIL - MODE SIMULE]")
        print(f"   Destinataire: {to}")
        print(f"   Sujet: {subject}")
        print(f"   Corps:\n{body}")
        if html:
            print(f"   HTML: {html[:200]}...")
        print("=" * 60)
        return True
    
    # Vérifier que les paramètres SMTP sont configurés
    smtp_email = params.get('SMTP_EMAIL', '')
    smtp_password = params.get('SMTP_MOT_DE_PASSE', '')
    
    if not smtp_email or not smtp_password:
        print("📧 [SMTP NON CONFIGURÉ] Email ou mot de passe manquant")
        print("=" * 60)
        print(f"📧 [EMAIL - MODE SIMULE]")
        print(f"   Destinataire: {to}")
        print(f"   Sujet: {subject}")
        print(f"   Corps:\n{body}")
        print("=" * 60)
        return True
    
    try:
        # Créer le message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_email
        msg['To'] = to if isinstance(to, str) else ', '.join(to)
        
        # Corps en texte
        part1 = MIMEText(body, 'plain')
        msg.attach(part1)
        
        # Corps en HTML
        if html:
            part2 = MIMEText(html, 'html')
            msg.attach(part2)
        
        # Envoyer
        server = smtplib.SMTP(params.get('SMTP_SERVEUR', 'smtp.gmail.com'), 
                              int(params.get('SMTP_PORT', 587)))
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()
        print(f"📧 Email envoyé à {to}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur SMTP: {str(e)}")
        print("=" * 60)
        print(f"📧 [EMAIL - FALLBACK CONSOLE]")
        print(f"   Destinataire: {to}")
        print(f"   Sujet: {subject}")
        print(f"   Corps:\n{body}")
        print("=" * 60)
        return True


def notifier_employe_conge(employe_email, nom_employe, type_conge, date_debut, date_fin, statut, commentaire=None):
    """
    Notifie un employé de l'approbation/refus de sa demande de congé
    """
    if not employe_email:
        print("⚠️ Pas d'email pour l'employé")
        return
    
    if statut == 'approuve':
        sujet = f"✅ Demande de congé approuvée - {type_conge}"
        corps = f"""
Bonjour {nom_employe},

Votre demande de congé {type_conge} a été approuvée.

Détails :
- Type : {type_conge}
- Période : du {date_debut} au {date_fin}
- Statut : Approuvé
{f"Commentaire : {commentaire}" if commentaire else ""}

Cordialement,
Direction des Ressources Humaines
DRET Oriental
"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #1f3864; color: white; padding: 15px; text-align: center; }}
        .content {{ padding: 20px; }}
        .footer {{ background: #f5f5f5; padding: 10px; text-align: center; font-size: 12px; color: #888; }}
        .status-approuve {{ color: #2e7d4f; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>✅ Demande de congé approuvée</h2>
        </div>
        <div class="content">
            <p>Bonjour <strong>{nom_employe}</strong>,</p>
            <p>Votre demande de congé <strong>{type_conge}</strong> a été <span class="status-approuve">approuvée</span>.</p>
            <p><strong>Détails :</strong></p>
            <ul>
                <li><strong>Type :</strong> {type_conge}</li>
                <li><strong>Période :</strong> du {date_debut} au {date_fin}</li>
                <li><strong>Statut :</strong> <span class="status-approuve">Approuvé</span></li>
                {"<li><strong>Commentaire :</strong> " + commentaire + "</li>" if commentaire else ""}
            </ul>
            <p>Cordialement,<br>Direction des Ressources Humaines<br>DRET Oriental</p>
        </div>
        <div class="footer">
            <p>DRET Oriental - Plateforme de gestion de la paie</p>
        </div>
    </div>
</body>
</html>
"""
    else:  # refuse
        sujet = f"❌ Demande de congé refusée - {type_conge}"
        corps = f"""
Bonjour {nom_employe},

Votre demande de congé {type_conge} a été refusée.

Détails :
- Type : {type_conge}
- Période : du {date_debut} au {date_fin}
- Statut : Refusé
{f"Motif : {commentaire}" if commentaire else ""}

Pour toute question, veuillez contacter votre responsable RH.

Cordialement,
Direction des Ressources Humaines
DRET Oriental
"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #b03a2e; color: white; padding: 15px; text-align: center; }}
        .content {{ padding: 20px; }}
        .footer {{ background: #f5f5f5; padding: 10px; text-align: center; font-size: 12px; color: #888; }}
        .status-refuse {{ color: #b03a2e; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>❌ Demande de congé refusée</h2>
        </div>
        <div class="content">
            <p>Bonjour <strong>{nom_employe}</strong>,</p>
            <p>Votre demande de congé <strong>{type_conge}</strong> a été <span class="status-refuse">refusée</span>.</p>
            <p><strong>Détails :</strong></p>
            <ul>
                <li><strong>Type :</strong> {type_conge}</li>
                <li><strong>Période :</strong> du {date_debut} au {date_fin}</li>
                <li><strong>Statut :</strong> <span class="status-refuse">Refusé</span></li>
                {"<li><strong>Motif :</strong> " + commentaire + "</li>" if commentaire else ""}
            </ul>
            <p>Pour toute question, veuillez contacter votre responsable RH.</p>
            <p>Cordialement,<br>Direction des Ressources Humaines<br>DRET Oriental</p>
        </div>
        <div class="footer">
            <p>DRET Oriental - Plateforme de gestion de la paie</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email(employe_email, sujet, corps, html)


def notifier_rh_nouvelle_demande(rh_emails, employe_nom, type_conge, date_debut, date_fin):
    """
    Notifie les RH d'une nouvelle demande de congé
    """
    if not rh_emails:
        print("⚠️ Pas d'emails RH")
        return
    
    sujet = f"📝 Nouvelle demande de congé - {employe_nom}"
    corps = f"""
Bonjour,

Une nouvelle demande de congé a été déposée.

Détails de la demande :
- Employé : {employe_nom}
- Type : {type_conge}
- Période : du {date_debut} au {date_fin}

Veuillez vous connecter à la plateforme pour traiter cette demande.

Cordialement,
Plateforme DRET Oriental
"""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2e5c8a; color: white; padding: 15px; text-align: center; }}
        .content {{ padding: 20px; }}
        .footer {{ background: #f5f5f5; padding: 10px; text-align: center; font-size: 12px; color: #888; }}
        .btn {{ display: inline-block; padding: 10px 20px; background: #2e5c8a; color: white; text-decoration: none; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>📝 Nouvelle demande de congé</h2>
        </div>
        <div class="content">
            <p>Bonjour,</p>
            <p>Une nouvelle demande de congé a été déposée par <strong>{employe_nom}</strong>.</p>
            <p><strong>Détails :</strong></p>
            <ul>
                <li><strong>Employé :</strong> {employe_nom}</li>
                <li><strong>Type :</strong> {type_conge}</li>
                <li><strong>Période :</strong> du {date_debut} au {date_fin}</li>
            </ul>
            <p><a href="http://localhost:5000/conges/gerer" style="display:inline-block;padding:10px 20px;background:#2e5c8a;color:white;text-decoration:none;border-radius:5px;">Traiter la demande</a></p>
            <p>Cordialement,<br>Plateforme DRET Oriental</p>
        </div>
        <div class="footer">
            <p>DRET Oriental - Plateforme de gestion de la paie</p>
        </div>
    </div>
</body>
</html>
"""
    
    send_email(rh_emails, sujet, corps, html)