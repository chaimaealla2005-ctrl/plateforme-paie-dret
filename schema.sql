-- ============================================================
-- SCHEMA BASE DE DONNEES - PLATEFORME DE GESTION DE LA PAIE
-- Multi-societe, parametrable, conforme a la loi marocaine
-- ============================================================

-- ------------------------------------------------------------
-- 1. SOCIETES (multi-tenant)
-- ------------------------------------------------------------
CREATE TABLE societe (
    id_societe INTEGER PRIMARY KEY AUTOINCREMENT,
    raison_sociale TEXT NOT NULL,
    ice TEXT,                          -- Identifiant Commun de l'Entreprise
    adresse TEXT,
    logo_path TEXT,
    date_creation TEXT DEFAULT CURRENT_TIMESTAMP,
    actif INTEGER DEFAULT 1
);

-- ------------------------------------------------------------
-- 2. UTILISATEURS ET ROLES
-- ------------------------------------------------------------
CREATE TABLE utilisateur (
    id_utilisateur INTEGER PRIMARY KEY AUTOINCREMENT,
    id_societe INTEGER,                -- NULL si super-admin (global)
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    mot_de_passe_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('super_admin', 'admin_societe', 'rh', 'comptable', 'employe')),
    actif INTEGER DEFAULT 1,
    date_creation TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_societe) REFERENCES societe(id_societe)
);

-- ------------------------------------------------------------
-- 3. EMPLOYES
-- ------------------------------------------------------------
CREATE TABLE employe (
    id_employe INTEGER PRIMARY KEY AUTOINCREMENT,
    id_societe INTEGER NOT NULL,
    id_utilisateur INTEGER,            -- lien optionnel si l'employe a un compte
    matricule TEXT NOT NULL,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    cin TEXT,
    cnss_numero TEXT,
    email TEXT,
    telephone TEXT,
    date_naissance TEXT,
    date_embauche TEXT NOT NULL,
    poste TEXT,
    grade TEXT,
    echelon TEXT,
    salaire_base REAL NOT NULL,
    rib TEXT,
    nb_personnes_a_charge INTEGER DEFAULT 0,
    actif INTEGER DEFAULT 1,
    FOREIGN KEY (id_societe) REFERENCES societe(id_societe),
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur),
    UNIQUE (id_societe, matricule)
);

-- ------------------------------------------------------------
-- 4. BAREMES DE COTISATIONS SOCIALES (CNSS, AMO...)
-- Prechargés avec la loi marocaine, modifiables si la loi change
-- ------------------------------------------------------------
CREATE TABLE bareme_cotisation (
    id_bareme INTEGER PRIMARY KEY AUTOINCREMENT,
    id_societe INTEGER,                -- NULL = barème global par défaut (loi marocaine)
    code TEXT NOT NULL,                -- 'CNSS', 'AMO'
    libelle TEXT NOT NULL,
    taux_salarial REAL NOT NULL,       -- en %
    taux_patronal REAL,                -- en %
    plafond_mensuel REAL,              -- NULL si pas de plafond
    annee_application INTEGER NOT NULL,
    actif INTEGER DEFAULT 1,
    FOREIGN KEY (id_societe) REFERENCES societe(id_societe)
);

-- ------------------------------------------------------------
-- 5. TRANCHES IR (barème progressif de l'impôt sur le revenu)
-- Prechargées avec la loi marocaine, modifiables si la loi change
-- ------------------------------------------------------------
CREATE TABLE tranche_ir (
    id_tranche INTEGER PRIMARY KEY AUTOINCREMENT,
    id_societe INTEGER,                -- NULL = barème global par défaut (loi marocaine)
    seuil_bas REAL NOT NULL,           -- borne basse annuelle en MAD
    seuil_haut REAL,                   -- borne haute annuelle en MAD (NULL = illimité)
    taux REAL NOT NULL,                -- en %
    somme_a_deduire REAL NOT NULL,     -- pour calcul rapide : IR = revenu*taux - somme_a_deduire
    annee_application INTEGER NOT NULL,
    FOREIGN KEY (id_societe) REFERENCES societe(id_societe)
);

-- ------------------------------------------------------------
-- 5bis. PARAMETRES LEGAUX GENERIQUES
-- Toute constante de la loi qui ne rentre pas dans les tables
-- precedentes : abattement frais professionnels, deduction
-- charges de famille, SMIG... Stockee en donnee, pas en code,
-- pour rester modifiable si la loi de finances change.
-- ------------------------------------------------------------
CREATE TABLE parametre_legal (
    id_parametre INTEGER PRIMARY KEY AUTOINCREMENT,
    id_societe INTEGER,                -- NULL = valeur légale par défaut
    code TEXT NOT NULL,                -- 'SMIG_HORAIRE', 'ABATTEMENT_SEUIL', ...
    libelle TEXT NOT NULL,
    valeur REAL NOT NULL,
    unite TEXT,                        -- 'MAD', '%', 'MAD/personne'...
    annee_application INTEGER NOT NULL,
    FOREIGN KEY (id_societe) REFERENCES societe(id_societe)
);

-- ------------------------------------------------------------
-- 6. CATALOGUE DES ELEMENTS DE PAIE (primes, indemnités, retenues)
-- Prechargé avec le catalogue légal marocain, extensible par société
-- ------------------------------------------------------------
CREATE TABLE element_paie (
    id_element INTEGER PRIMARY KEY AUTOINCREMENT,
    id_societe INTEGER,                -- NULL = élément légal global (catalogue par défaut)
    code TEXT NOT NULL,                -- 'PRIME_ANCIENNETE', 'IND_TRANSPORT', ...
    libelle TEXT NOT NULL,
    type_element TEXT NOT NULL CHECK (type_element IN ('prime', 'indemnite', 'retenue')),
    mode_calcul TEXT NOT NULL CHECK (mode_calcul IN ('montant_fixe', 'pourcentage_base', 'bareme_anciennete')),
    valeur REAL,                       -- montant fixe OU pourcentage selon mode_calcul
    plafond_exoneration REAL,          -- NULL si pas de plafond
    soumis_cnss INTEGER DEFAULT 1,     -- 1 = oui, 0 = non (au-delà du plafond, devient 1 automatiquement)
    soumis_ir INTEGER DEFAULT 1,
    obligatoire INTEGER DEFAULT 0,     -- 1 pour la prime d'ancienneté par exemple
    actif INTEGER DEFAULT 1,
    FOREIGN KEY (id_societe) REFERENCES societe(id_societe)
);

-- Paliers pour les éléments calculés par barème (ex: prime d'ancienneté)
CREATE TABLE palier_element (
    id_palier INTEGER PRIMARY KEY AUTOINCREMENT,
    id_element INTEGER NOT NULL,
    annees_min INTEGER NOT NULL,
    annees_max INTEGER,                 -- NULL = illimité
    taux REAL NOT NULL,                 -- en %
    FOREIGN KEY (id_element) REFERENCES element_paie(id_element)
);

-- ------------------------------------------------------------
-- 7. AFFECTATION DES ELEMENTS DE PAIE AUX EMPLOYES
-- (quels éléments s'appliquent à quel employé, avec valeur spécifique éventuelle)
-- ------------------------------------------------------------
CREATE TABLE employe_element (
    id_employe_element INTEGER PRIMARY KEY AUTOINCREMENT,
    id_employe INTEGER NOT NULL,
    id_element INTEGER NOT NULL,
    valeur_specifique REAL,             -- surcharge la valeur par défaut si besoin
    date_debut TEXT NOT NULL,
    date_fin TEXT,
    FOREIGN KEY (id_employe) REFERENCES employe(id_employe),
    FOREIGN KEY (id_element) REFERENCES element_paie(id_element)
);

-- ------------------------------------------------------------
-- 8. BULLETINS DE PAIE
-- ------------------------------------------------------------
CREATE TABLE bulletin_paie (
    id_bulletin INTEGER PRIMARY KEY AUTOINCREMENT,
    id_employe INTEGER NOT NULL,
    mois INTEGER NOT NULL,
    annee INTEGER NOT NULL,
    salaire_base REAL NOT NULL,
    total_primes_indemnites REAL NOT NULL,
    salaire_brut REAL NOT NULL,
    total_cnss REAL NOT NULL,
    total_amo REAL NOT NULL,
    salaire_net_imposable REAL NOT NULL,
    total_ir REAL NOT NULL,
    total_retenues_autres REAL DEFAULT 0,
    salaire_net_a_payer REAL NOT NULL,
    date_generation TEXT DEFAULT CURRENT_TIMESTAMP,
    pdf_path TEXT,
    FOREIGN KEY (id_employe) REFERENCES employe(id_employe),
    UNIQUE (id_employe, mois, annee)
);

-- Detail ligne par ligne de chaque bulletin (traçabilité complète)
CREATE TABLE ligne_bulletin (
    id_ligne INTEGER PRIMARY KEY AUTOINCREMENT,
    id_bulletin INTEGER NOT NULL,
    id_element INTEGER,                 -- NULL pour les lignes de cotisation/IR
    libelle TEXT NOT NULL,
    montant REAL NOT NULL,
    type_ligne TEXT NOT NULL CHECK (type_ligne IN ('gain', 'cotisation', 'impot', 'retenue')),
    FOREIGN KEY (id_bulletin) REFERENCES bulletin_paie(id_bulletin),
    FOREIGN KEY (id_element) REFERENCES element_paie(id_element)
);

-- ------------------------------------------------------------
-- 9. JOURNAL DE TRACABILITE
-- ------------------------------------------------------------
CREATE TABLE journal_action (
    id_action INTEGER PRIMARY KEY AUTOINCREMENT,
    id_utilisateur INTEGER,
    id_societe INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    date_action TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur),
    FOREIGN KEY (id_societe) REFERENCES societe(id_societe)
);

-- Ajouter les colonnes manquantes à la table societe
ALTER TABLE societe ADD COLUMN cnss VARCHAR(20);
ALTER TABLE societe ADD COLUMN rc VARCHAR(20);


-- ============================================================
-- TABLE DES CONGES
-- ============================================================

-- Types de congés
CREATE TABLE IF NOT EXISTS type_conge (
    id_type_conge INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    libelle TEXT NOT NULL,
    jours_par_an INTEGER DEFAULT 30,
    cumulable INTEGER DEFAULT 1,
    actif INTEGER DEFAULT 1
);

-- Demandes de congé
CREATE TABLE IF NOT EXISTS conge (
    id_conge INTEGER PRIMARY KEY AUTOINCREMENT,
    id_employe INTEGER NOT NULL,
    id_type_conge INTEGER NOT NULL,
    date_debut TEXT NOT NULL,
    date_fin TEXT NOT NULL,
    nb_jours_ouvres REAL NOT NULL,
    statut TEXT NOT NULL CHECK (statut IN ('en_attente', 'approuve', 'refuse', 'annule')),
    motif TEXT,
    date_demande TEXT DEFAULT CURRENT_TIMESTAMP,
    date_reponse TEXT,
    id_utilisateur_reponse INTEGER,
    commentaire_reponse TEXT,
    FOREIGN KEY (id_employe) REFERENCES employe(id_employe),
    FOREIGN KEY (id_type_conge) REFERENCES type_conge(id_type_conge),
    FOREIGN KEY (id_utilisateur_reponse) REFERENCES utilisateur(id_utilisateur)
);

-- Soldes de congés
CREATE TABLE IF NOT EXISTS solde_conge (
    id_solde INTEGER PRIMARY KEY AUTOINCREMENT,
    id_employe INTEGER NOT NULL,
    id_type_conge INTEGER NOT NULL,
    annee INTEGER NOT NULL,
    jours_acquis REAL DEFAULT 0,
    jours_pris REAL DEFAULT 0,
    jours_restants REAL DEFAULT 0,
    FOREIGN KEY (id_employe) REFERENCES employe(id_employe),
    FOREIGN KEY (id_type_conge) REFERENCES type_conge(id_type_conge),
    UNIQUE (id_employe, id_type_conge, annee)
);

-- Ajouter les colonnes pour les informations personnelles
ALTER TABLE employe ADD COLUMN situation_familiale TEXT DEFAULT 'MARIE';
ALTER TABLE employe ADD COLUMN cnss_numero TEXT;
ALTER TABLE employe ADD COLUMN jours_travailles INTEGER DEFAULT 26;
ALTER TABLE employe ADD COLUMN heures_sup REAL DEFAULT 0;

-- Ajouter la colonne pour stocker le chemin du fichier
ALTER TABLE conge ADD COLUMN piece_jointe TEXT;

CREATE TABLE parametre_notification (
    id_parametre INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    valeur TEXT NOT NULL,
    description TEXT
);

-- Ajouter la table d'historique des paramètres
CREATE TABLE IF NOT EXISTS historique_parametres (
    id_historique INTEGER PRIMARY KEY AUTOINCREMENT,
    id_utilisateur INTEGER NOT NULL,
    id_societe INTEGER,
    categorie TEXT NOT NULL,  -- 'bareme_cotisation', 'tranche_ir', 'parametre_legal', 'element_paie'
    id_element INTEGER,        -- ID de l'élément modifié
    code_element TEXT,         -- Code de l'élément (ex: 'CNSS', 'IR_TRANCHE_1')
    ancienne_valeur TEXT,
    nouvelle_valeur TEXT,
    champ_modifie TEXT,
    date_modification TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur),
    FOREIGN KEY (id_societe) REFERENCES societe(id_societe)
);

ALTER TABLE conge ADD COLUMN verrouille INTEGER DEFAULT 0;

-- Ajouter les colonnes pour les mentions légales
ALTER TABLE societe ADD COLUMN cnss VARCHAR(20);
ALTER TABLE societe ADD COLUMN rc VARCHAR(20);
ALTER TABLE societe ADD COLUMN telephone VARCHAR(20);
ALTER TABLE societe ADD COLUMN email VARCHAR(100);

-- Ajouter la colonne mode_paiement à la table societe
ALTER TABLE societe ADD COLUMN mode_paiement TEXT DEFAULT 'Virement bancaire / Chèque';

-- Ajouter la colonne logo_path si elle n'existe pas
ALTER TABLE societe ADD COLUMN logo_path TEXT;