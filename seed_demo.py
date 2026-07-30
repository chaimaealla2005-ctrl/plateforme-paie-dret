"""
Cree des donnees de demonstration (societe, utilisateurs, employe) pour
pouvoir tester la plateforme immediatement apres l'installation.

Comptes crees :
  - super.admin@plateforme.ma   / admin123   (super_admin)
  - admin@dret-demo.ma          / admin123   (admin_societe)
  - rh@dret-demo.ma             / rh123      (rh)
  - comptable@dret-demo.ma      / compta123  (comptable)
"""
from werkzeug.security import generate_password_hash


def creer_donnees_demo(db):
    # Une societe de demonstration
    db.execute(
        "INSERT INTO societe (raison_sociale, ice, adresse) VALUES (?, ?, ?)",
        ("Société Démo DRET", "00123456000078", "Oujda, Oriental"),
    )
    id_societe = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    # Super-admin (aucune societe rattachee : id_societe = NULL)
    db.execute(
        """INSERT INTO utilisateur (id_societe, nom, prenom, email, mot_de_passe_hash, role)
           VALUES (NULL, ?, ?, ?, ?, ?)""",
        ("Admin", "Super", "super.admin@plateforme.ma",
         generate_password_hash("admin123"), "super_admin"),
    )

    # Admin de la societe demo (est aussi un employe : il a un salaire, une fiche RH)
    db.execute(
        """INSERT INTO utilisateur (id_societe, nom, prenom, email, mot_de_passe_hash, role)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (id_societe, "Alami", "Karim", "admin@dret-demo.ma",
         generate_password_hash("admin123"), "admin_societe"),
    )
    id_utilisateur_admin = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    db.execute(
        """INSERT INTO employe (id_societe, id_utilisateur, matricule, nom, prenom, date_embauche,
                                 poste, grade, salaire_base, nb_personnes_a_charge)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (id_societe, id_utilisateur_admin, "EMP-ADM", "Alami", "Karim", "2018-01-15",
         "Administrateur société", "Cadre supérieur", 15000, 1),
    )

    # RH (est aussi un employe)
    db.execute(
        """INSERT INTO utilisateur (id_societe, nom, prenom, email, mot_de_passe_hash, role)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (id_societe, "Bennani", "Sara", "rh@dret-demo.ma",
         generate_password_hash("rh123"), "rh"),
    )
    id_utilisateur_rh = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    db.execute(
        """INSERT INTO employe (id_societe, id_utilisateur, matricule, nom, prenom, date_embauche,
                                 poste, grade, salaire_base, nb_personnes_a_charge)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (id_societe, id_utilisateur_rh, "EMP-RH1", "Bennani", "Sara", "2020-06-01",
         "Responsable RH", "Cadre", 10000, 0),
    )

    # Comptable (est aussi un employe)
    db.execute(
        """INSERT INTO utilisateur (id_societe, nom, prenom, email, mot_de_passe_hash, role)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (id_societe, "Tazi", "Youssef", "comptable@dret-demo.ma",
         generate_password_hash("compta123"), "comptable"),
    )
    id_utilisateur_comptable = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    db.execute(
        """INSERT INTO employe (id_societe, id_utilisateur, matricule, nom, prenom, date_embauche,
                                 poste, grade, salaire_base, nb_personnes_a_charge)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (id_societe, id_utilisateur_comptable, "EMP-CPT", "Tazi", "Youssef", "2021-09-01",
         "Comptable", "Agent de maîtrise", 8500, 0),
    )

    # Un employe de demonstration (7 ans d'anciennete environ, pour tester la prime)
    db.execute(
        """INSERT INTO employe (id_societe, matricule, nom, prenom, cin, date_embauche,
                                 poste, grade, salaire_base, rib, nb_personnes_a_charge)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (id_societe, "EMP001", "Idrissi", "Fatima", "AB123456", "2019-03-01",
         "Ingénieur", "Cadre", 8000, "007780000123456789012345", 2),
    )
    id_employe = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    # Affecter l'indemnite de transport (element legal global) a cet employe
    id_transport = db.execute(
        "SELECT id_element FROM element_paie WHERE code = 'IND_TRANSPORT'"
    ).fetchone()["id_element"]
    db.execute(
        """INSERT INTO employe_element (id_employe, id_element, date_debut)
           VALUES (?, ?, date('now'))""",
        (id_employe, id_transport),
    )

    # Affecter aussi la prime d'anciennete (calculee automatiquement par palier)
    id_anciennete = db.execute(
        "SELECT id_element FROM element_paie WHERE code = 'PRIME_ANCIENNETE'"
    ).fetchone()["id_element"]
    db.execute(
        """INSERT INTO employe_element (id_employe, id_element, date_debut)
           VALUES (?, ?, date('now'))""",
        (id_employe, id_anciennete),
    )

    db.commit()