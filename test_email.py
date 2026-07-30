# test_email.py
from utils.email import send_email

# Tester l'envoi d'un email simple
send_email(
    to='chaimaealla2005@gmail.com',  # Remplace par ton email
    subject='🧪 Test de notification',
    body='Ceci est un test de la plateforme DRET Oriental.',
    html='<h1>Test</h1><p>Ceci est un test de la plateforme.</p>'
)
print("✅ Email test envoyé (ou affiché dans la console)")