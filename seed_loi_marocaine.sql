-- ============================================================
-- PRECHARGEMENT DE LA LOI MAROCAINE DU SALAIRE - ANNEE 2026
-- ============================================================
-- COTISATIONS SOCIALES COMPLETES
-- ============================================================
INSERT OR IGNORE INTO bareme_cotisation (id_societe, code, libelle, taux_salarial, taux_patronal, plafond_mensuel, annee_application) VALUES
(NULL, 'CNSS', 'Cotisation CNSS (prestations sociales)', 4.48, 9.48, 6000.00, 2026),
(NULL, 'AMO', 'Cotisation AMO (assurance maladie obligatoire)', 2.26, 4.11, NULL, 2026),
(NULL, 'IPE', 'Indemnité perte d''emploi', 0.19, 0.00, 6000.00, 2026),
(NULL, 'Mutuelle', 'Mutuelle santé (complémentaire facultative)', 2.59, 2.59, NULL, 2026),
(NULL, 'CIMR', 'Cotisation CIMR (retraite complémentaire)', 3.00, 3.90, NULL, 2026);

-- ============================================================
-- COTISATIONS PATRONALES
-- ============================================================
INSERT OR IGNORE INTO bareme_cotisation (id_societe, code, libelle, taux_salarial, taux_patronal, plafond_mensuel, annee_application) VALUES
(NULL, 'ALLOC_FAM', 'Allocation familiale (patronale)', 0, 6.40, 6000.00, 2026),
(NULL, 'PREST_SOC', 'Prestations sociales (patronale)', 0, 8.98, 6000.00, 2026),
(NULL, 'TAXE_FORM', 'Taxe formation professionnelle (patronale)', 0, 1.60, 6000.00, 2026);

-- ============================================================
-- TRANCHES IR - BAREME ANNUEL 2026 
-- ============================================================
-- ============================================================
-- TRANCHES IR - BAREME ANNUEL 2026 (CORRIGE)
-- ============================================================
INSERT OR IGNORE INTO tranche_ir (id_societe, seuil_bas, seuil_haut, taux, somme_a_deduire, annee_application) VALUES
(NULL, 0, 40000.00, 0, 0, 2026),
(NULL, 40000.01, 60000.00, 10, 4000, 2026),
(NULL, 60000.01, 80000.00, 20, 10000, 2026),
(NULL, 80000.01, 100000.00, 30, 18000, 2026),
(NULL, 100000.01, 180000.00, 34, 22000, 2026),
(NULL, 180000.01, NULL, 37, 29200, 2026);

-- PARAMETRES LEGAUX
INSERT OR IGNORE INTO parametre_legal (id_societe, code, libelle, valeur, unite, annee_application) VALUES
(NULL, 'SMIG_HORAIRE', 'SMIG horaire', 16.29, 'MAD/heure', 2026),
(NULL, 'ABATTEMENT_SEUIL', 'Seuil mensuel pour taux d''abattement bas', 6500, 'MAD', 2026),
(NULL, 'ABATTEMENT_TAUX_BAS', 'Taux d''abattement si brut <= seuil', 35, '%', 2026),
(NULL, 'ABATTEMENT_TAUX_HAUT', 'Taux d''abattement si brut > seuil', 25, '%', 2026),
(NULL, 'CHARGE_FAMILLE_MONTANT', 'Déduction IR par personne à charge', 50, 'MAD/personne', 2026),
(NULL, 'CHARGE_FAMILLE_PLAFOND', 'Plafond mensuel de la déduction charges de famille', 300, 'MAD', 2026),
(NULL, 'TAUX_CNSS', 'Taux CNSS salarial', 4.48, '%', 2026),
(NULL, 'TAUX_AMO', 'Taux AMO salarial', 2.26, '%', 2026),
(NULL, 'TAUX_ALLOC_FAMILIALE', 'Taux allocation familiale (patronal)', 6.40, '%', 2026),
(NULL, 'TAUX_PRESTATIONS_SOCIALES', 'Taux prestations sociales (patronal)', 8.98, '%', 2026),
(NULL, 'TAUX_TAXE_FORMATION', 'Taux taxe formation professionnelle', 1.60, '%', 2026),
(NULL, 'TAUX_AMO_PATRONAL', 'Taux AMO patronal', 4.11, '%', 2026),
(NULL, 'TAUX_MUTUELLE', 'Taux mutuelle santé', 2.59, '%', 2026),
(NULL, 'TAUX_CIMR_SALARIAL', 'Taux CIMR salarial', 3.00, '%', 2026),
(NULL, 'TAUX_CIMR_PATRONAL', 'Taux CIMR patronal', 3.90, '%', 2026),
(NULL, 'TAUX_PERTE_EMPLOI', 'Taux indemnite perte d''emploi', 0.19, '%', 2026);

-- CATALOGUE DES ELEMENTS DE PAIE
INSERT OR IGNORE INTO element_paie (id_societe, code, libelle, type_element, mode_calcul, valeur, plafond_exoneration, soumis_cnss, soumis_ir, obligatoire) VALUES
(NULL, 'PRIME_ANCIENNETE', 'Prime d''ancienneté', 'prime', 'bareme_anciennete', NULL, NULL, 1, 1, 1);

INSERT OR IGNORE INTO palier_element (id_element, annees_min, annees_max, taux)
SELECT id_element, 2, 5, 5 FROM element_paie WHERE code = 'PRIME_ANCIENNETE'
UNION ALL SELECT id_element, 5, 12, 10 FROM element_paie WHERE code = 'PRIME_ANCIENNETE'
UNION ALL SELECT id_element, 12, 20, 15 FROM element_paie WHERE code = 'PRIME_ANCIENNETE'
UNION ALL SELECT id_element, 20, 25, 20 FROM element_paie WHERE code = 'PRIME_ANCIENNETE'
UNION ALL SELECT id_element, 25, NULL, 25 FROM element_paie WHERE code = 'PRIME_ANCIENNETE';

INSERT OR IGNORE INTO element_paie (id_societe, code, libelle, type_element, mode_calcul, valeur, plafond_exoneration, soumis_cnss, soumis_ir, obligatoire) VALUES
(NULL, 'IND_TRANSPORT', 'Indemnité de transport (zone urbaine)', 'indemnite', 'montant_fixe', 500.00, 500.00, 0, 0, 0),
(NULL, 'IND_REPRESENTATION', 'Indemnité de représentation', 'indemnite', 'pourcentage_base', 10.00, 10.00, 0, 0, 0),
(NULL, 'IND_PANIER', 'Indemnité de panier / restauration', 'indemnite', 'montant_fixe', 200.00, 200.00, 0, 0, 0),
(NULL, 'IND_CAISSE', 'Indemnité de caisse', 'indemnite', 'montant_fixe', 190.00, 190.00, 0, 0, 0),
(NULL, 'IND_SALISSURE', 'Indemnité de salissure', 'indemnite', 'montant_fixe', 210.00, 210.00, 0, 0, 0),
(NULL, 'PRIME_RENDEMENT', 'Prime de rendement / performance', 'prime', 'montant_fixe', 0, NULL, 1, 1, 0);

-- TYPES DE CONGES
INSERT OR IGNORE INTO type_conge (code, libelle, jours_par_an, cumulable) VALUES
('CP', 'Congé payé annuel', 30, 1),
('CPS', 'Congé payé supplémentaire (ancienneté)', 0, 1),
('MALADIE', 'Congé maladie', 0, 0),
('EXCEPTIONNEL', 'Congé exceptionnel', 0, 0),
('SANS_SOLDE', 'Congé sans solde', 0, 0);

-- Paramètres légaux pour le calcul mensuel
INSERT OR IGNORE INTO parametre_legal (id_societe, code, libelle, valeur, unite, annee_application) VALUES
(NULL, 'IR_TAUX_MAX', 'Taux maximal IR', 38, '%', 2026),
(NULL, 'IR_PLAFOND_MENSUEL', 'Plafond mensuel pour IR', 15000, 'MAD', 2026);

INSERT OR IGNORE INTO parametre_notification (code, valeur, description) VALUES
('SMTP_SERVEUR', 'smtp.gmail.com', 'Serveur SMTP'),
('SMTP_PORT', '587', 'Port SMTP'),
('SMTP_EMAIL', 'notification@plateforme-paie.ma', 'Email d''envoi'),
('SMTP_MOT_DE_PASSE', '', 'Mot de passe d''application Gmail'),
('NOM_EXPEDITEUR', 'Plateforme Paie - DRET Oriental', 'Nom affiché dans les emails'),
('ACTIVER_NOTIFICATIONS', '1', '1 = activé, 0 = désactivé');


-- Ajouter les cotisations manquantes dans la base
INSERT OR IGNORE INTO bareme_cotisation (id_societe, code, libelle, taux_salarial, taux_patronal, plafond_mensuel, annee_application) VALUES
(NULL, 'IPE', 'Indemnité perte d''emploi', 0.19, 0, 6000.00, 2026),
(NULL, 'Mutuelle', 'Mutuelle santé (complémentaire facultative)', 2.59, 2.59, NULL, 2026),
(NULL, 'CIMR_SALARIAL', 'CIMR (retraite complémentaire) - part salariale', 3.00, 0, NULL, 2026),
(NULL, 'CIMR_PATRONAL', 'CIMR (retraite complémentaire) - part patronale', 0, 3.90, NULL, 2026),
(NULL, 'ALLOC_FAM', 'Allocation familiale - part patronale', 0, 6.40, 6000.00, 2026),
(NULL, 'PREST_SOC', 'Prestations sociales - part patronale', 0, 8.98, 6000.00, 2026),
(NULL, 'TAXE_FORM', 'Taxe formation professionnelle', 0, 1.60, 6000.00, 2026),
(NULL, 'AMO_PATRONAL', 'AMO - part patronale', 0, 4.11, NULL, 2026);