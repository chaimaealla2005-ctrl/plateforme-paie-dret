import sqlite3

conn = sqlite3.connect('database.db')
c = conn.cursor()

try:
    c.execute('ALTER TABLE employe ADD COLUMN jours_travailles INTEGER DEFAULT 26')
    print('OK jours_travailles')
except:
    print('deja jours_travailles')

try:
    c.execute("ALTER TABLE employe ADD COLUMN situation_familiale TEXT DEFAULT 'MARIE'")
    print('OK situation_familiale')
except:
    print('deja situation_familiale')

try:
    c.execute('ALTER TABLE employe ADD COLUMN cnss_numero TEXT')
    print('OK cnss_numero')
except:
    print('deja cnss_numero')

try:
    c.execute('ALTER TABLE employe ADD COLUMN heures_sup REAL DEFAULT 0')
    print('OK heures_sup')
except:
    print('deja heures_sup')

c.execute("UPDATE employe SET jours_travailles=26, situation_familiale='MARIE', cnss_numero='123456789', heures_sup=0 WHERE matricule='CP268'")
conn.commit()
conn.close()

print('Termine !')