# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "change-moi-en-production-cle-secrete"
    DATABASE = os.path.join(BASE_DIR, "database.db")
    
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    
    # Upload configuration
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'conges')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 Mo
    
    # ============================================
    # EMAIL CONFIGURATION
    # ============================================
    MAIL_SERVER = 'smtp.gmail.com'  # ou smtp.office365.com, etc.
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'votre-email@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'votre-mot-de-passe')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'votre-email@gmail.com')
    
    # Pour les tests en développement, utiliser un fichier local
    # MAIL_SUPPRESS_SEND = True  # Désactiver pour la production
    
    # Activation des notifications par email
    ENABLE_EMAIL_NOTIFICATIONS = True