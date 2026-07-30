
import sqlite3
conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute('SELECT id_societe, raison_sociale, logo_path FROM societe')
rows = c.fetchall()
print('Sociétés:')
for r in rows:
    print(f'  {r[0]} - {r[1]} - logo: {r[2] or "None"}')
conn.close()