# reset_db.py
import sqlite3
import os

# Supprimer l'ancienne base si elle existe
if os.path.exists('database.db'):
    os.remove('database.db')

conn = sqlite3.connect('database.db')

# 1. Créer les tables (avec IF NOT EXISTS)
with open('schema.sql', 'r', encoding='utf-8') as f:
    sql = f.read()
    # Remplacer les ALTER TABLE par des CREATE TABLE IF NOT EXISTS
    # Exécuter chaque instruction séparément
    for statement in sql.split(';'):
        if statement.strip():
            try:
                conn.execute(statement)
            except sqlite3.OperationalError as e:
                if 'duplicate column name' not in str(e):
                    print(f"⚠️ Erreur: {e}")
                    print(f"   Statement: {statement[:100]}...")

# 2. Importer les données légales
with open('seed_loi_marocaine.sql', 'r', encoding='utf-8') as f:
    try:
        conn.executescript(f.read())
    except sqlite3.OperationalError as e:
        print(f"⚠️ Erreur seed: {e}")

# 3. Créer les comptes de démonstration
try:
    from seed_demo import creer_donnees_demo
    creer_donnees_demo(conn)
    print('✅ Comptes de démonstration créés')
except Exception as e:
    print(f"⚠️ Erreur comptes: {e}")

conn.commit()
conn.close()
print('✅ Base de données créée avec succès')
print('\n📋 Comptes de démonstration:')
print('  super.admin@plateforme.ma / admin123 (Super Admin)')
print('  admin@dret-demo.ma / admin123 (Admin Société)')
print('  rh@dret-demo.ma / rh123 (RH)')
print('  comptable@dret-demo.ma / compta123 (Comptable)')
print('  employe@dret-demo.ma / employe123 (Employé)')