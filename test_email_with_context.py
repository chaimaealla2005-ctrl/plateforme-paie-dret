# test_email_with_context.py
from app import create_app
from utils.email import send_email

app = create_app()

with app.app_context():
    result = send_email(
        to='chaimaealla2005@gmail.com',
        subject='🧪 Test de notification avec contexte',
        body='Ceci est un test depuis la plateforme DRET Oriental.',
        html='<h1>Test</h1><p>Ceci est un test de la plateforme.</p>'
    )
    print(f"✅ Résultat: {result}")