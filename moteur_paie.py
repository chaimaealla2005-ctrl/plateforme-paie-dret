"""
Moteur de calcul de la paie - Plateforme DRET Oriental
--------------------------------------------------------
Ce module calcule un bulletin de paie en se basant sur les
donnees stockees en base (bareme_cotisation, tranche_ir,
element_paie, palier_element) plutot que sur des valeurs
codees en dur. Ainsi, si la loi marocaine change (nouvelle
loi de finances), il suffit de mettre a jour les donnees,
pas le code.

Utilisation typique :
    resultat = calculer_bulletin(id_employe=3, mois=7, annee=2026, connexion=db)
"""

from datetime import date


# ============================================================
# 1. CALCUL DE L'ANCIENNETE (en annees completes)
# ============================================================
def calculer_anciennete(date_embauche_str, date_reference=None):
    date_embauche = date.fromisoformat(date_embauche_str)
    ref = date_reference or date.today()
    annees = ref.year - date_embauche.year
    if (ref.month, ref.day) < (date_embauche.month, date_embauche.day):
        annees -= 1
    return max(annees, 0)


# ============================================================
# 2. CALCUL D'UN ELEMENT DE PAIE (prime/indemnite) SELON SON MODE
# ============================================================
def calculer_montant_element(element, salaire_base, anciennete, paliers=None):
    """
    element : dict issu de la table element_paie
    paliers : liste de dicts issus de palier_element (si mode = bareme_anciennete)
    """
    mode = element["mode_calcul"]

    if mode == "montant_fixe":
        return element["valeur"] or 0

    if mode == "pourcentage_base":
        # CORRECTION : appliquer le pourcentage sur le salaire de base
        return round(salaire_base * (element["valeur"] / 100), 2)

    if mode == "bareme_anciennete":
        if not paliers:
            return 0
        taux_applicable = 0
        for palier in paliers:
            borne_max = palier["annees_max"] if palier["annees_max"] is not None else float("inf")
            if palier["annees_min"] <= anciennete < borne_max:
                taux_applicable = palier["taux"]
                break
            # cas special : au-dela du dernier palier (borne_max = None => illimite)
            if palier["annees_max"] is None and anciennete >= palier["annees_min"]:
                taux_applicable = palier["taux"]
        # CORRECTION : appliquer le taux sur le salaire de base
        return round(salaire_base * (taux_applicable / 100), 2)

    return 0


# ============================================================
# 3. DETERMINER LA PART EXONEREE / IMPOSABLE D'UN ELEMENT
# ============================================================
def repartir_exoneration(montant, plafond_exoneration):
    """
    Retourne (part_exoneree, part_imposable).
    Si le montant depasse le plafond, la difference devient imposable
    (CNSS + IR), meme si l'element etait defini comme "exonere".
    """
    if plafond_exoneration is None:
        return 0, montant  # pas de regle d'exoneration -> tout est imposable
    if montant <= plafond_exoneration:
        return montant, 0
    return plafond_exoneration, montant - plafond_exoneration


# ============================================================
# 4. CALCUL DES COTISATIONS (CNSS + AMO)
# ============================================================
def calculer_cotisations(salaire_brut_cotisable, baremes):
    """
    baremes : liste de dicts issus de bareme_cotisation (CNSS, AMO)
    Retourne un dict {'CNSS': montant, 'AMO': montant}
    """
    resultats = {}
    for bareme in baremes:
        base = salaire_brut_cotisable
        if bareme["plafond_mensuel"] is not None:
            base = min(base, bareme["plafond_mensuel"])
        montant = round(base * (bareme["taux_salarial"] / 100), 2)
        resultats[bareme["code"]] = montant
    return resultats


# ============================================================
# 5. CALCUL DE L'IR (impot sur le revenu)
# ============================================================
# moteur_paie.py - Fonction calculer_ir (version corrigée)

def calculer_ir(salaire_net_imposable_mensuel, tranches, parametres, nb_personnes_a_charge=0):
    """
    Calcule l'IR selon le barème ANNUEL marocain 2026.
    Les tranches sont en valeurs annuelles.
    """
    # 1. Abattement frais professionnels (paramétrable)
    seuil = parametres.get("ABATTEMENT_SEUIL", 6500)
    taux_bas = parametres.get("ABATTEMENT_TAUX_BAS", 35)
    taux_haut = parametres.get("ABATTEMENT_TAUX_HAUT", 25)
    
    # Abattement sur le montant mensuel
    if salaire_net_imposable_mensuel <= seuil:
        abattement = salaire_net_imposable_mensuel * (taux_bas / 100)
    else:
        abattement = salaire_net_imposable_mensuel * (taux_haut / 100)
    
    # Revenu après abattement (mensuel puis annuel)
    revenu_apres_abattement_mensuel = salaire_net_imposable_mensuel - abattement
    revenu_apres_abattement_annuel = revenu_apres_abattement_mensuel * 12
    
    # 2. Application du barème progressif ANNUEL
    ir_annuel = 0
    for tranche in tranches:
        seuil_bas = tranche["seuil_bas"]
        seuil_haut = tranche["seuil_haut"] if tranche["seuil_haut"] is not None else float("inf")
        taux = tranche["taux"]
        somme_a_deduire = tranche["somme_a_deduire"]
        
        if seuil_bas <= revenu_apres_abattement_annuel <= seuil_haut:
            ir_annuel = (revenu_apres_abattement_annuel * (taux / 100)) - somme_a_deduire
            break
    
    ir_annuel = max(ir_annuel, 0)
    ir_mensuel = ir_annuel / 12
    
    # 3. Déduction pour charges de famille
    montant_par_personne = parametres.get("CHARGE_FAMILLE_MONTANT", 50)
    plafond_deduction = parametres.get("CHARGE_FAMILLE_PLAFOND", 300)
    
    deduction_charges = min(nb_personnes_a_charge * montant_par_personne, plafond_deduction)
    ir_mensuel = max(ir_mensuel - deduction_charges, 0)
    
    return round(ir_mensuel, 2)


# moteur_paie.py - Fonction calculer_bulletin MODIFIEE

def calculer_bulletin(employe, elements_employe, baremes_cotisation, tranches_ir, parametres_legaux):
    """
    employe : dict (salaire_base, date_embauche, nb_personnes_a_charge...)
    elements_employe : liste de dicts {element: {...}, paliers: [...]}
    baremes_cotisation : liste de dicts (CNSS, AMO)
    tranches_ir : liste de dicts (bareme IR)
    parametres_legaux : dict (abattement, charges de famille...) issu de parametre_legal

    Retourne un dict detaillant chaque etape du calcul.
    """
    salaire_base = employe["salaire_base"]
    anciennete = calculer_anciennete(employe["date_embauche"])

    lignes_gains = []
    total_gains = 0
    total_cnss_base = salaire_base
    total_ir_base = salaire_base

    # ============================================================
    # 1. RECHERCHE DE LA PRIME D'ANCIENNETE (AUTOMATIQUE)
    # ============================================================
    # Vérifier si la prime d'ancienneté est déjà dans elements_employe
    prime_anciennete_trouvee = False
    for item in elements_employe:
        if item["element"].get("code") == "PRIME_ANCIENNETE":
            prime_anciennete_trouvee = True
            break
    
    # Si elle n'est pas trouvée, l'ajouter automatiquement
    if not prime_anciennete_trouvee:
        # Récupérer l'élément PRIME_ANCIENNETE depuis la base
        import sqlite3
        from db import get_db
        db = get_db()
        element = db.execute(
            "SELECT * FROM element_paie WHERE code = ?",
            ('PRIME_ANCIENNETE',)
        ).fetchone()
        if element:
            # Récupérer les paliers
            paliers = db.execute(
                "SELECT * FROM palier_element WHERE id_element = ? ORDER BY annees_min",
                (element["id_element"],)
            ).fetchall()
            # Ajouter la prime aux éléments
            elements_employe.append({
                "element": dict(element),
                "paliers": [dict(p) for p in paliers] if paliers else None
            })
            print("✅ Prime d'ancienneté ajoutée automatiquement au calcul")

    # 2. Calcul de chaque prime/indemnite
    for item in elements_employe:
        element = item["element"]
        paliers = item.get("paliers")
        montant = calculer_montant_element(element, salaire_base, anciennete, paliers)

        part_exoneree, part_imposable = repartir_exoneration(montant, element["plafond_exoneration"])

        lignes_gains.append({
            "libelle": element["libelle"],
            "montant": montant,
            "soumis_cnss": bool(element["soumis_cnss"]) or part_imposable > 0,
            "soumis_ir": bool(element["soumis_ir"]) or part_imposable > 0,
        })

        total_gains += montant
        
        if element["soumis_cnss"]:
            total_cnss_base += montant
        elif part_imposable > 0:
            total_cnss_base += part_imposable
            
        if element["soumis_ir"]:
            total_ir_base += montant
        elif part_imposable > 0:
            total_ir_base += part_imposable

    # 3. Salaire brut
    salaire_brut = round(salaire_base + total_gains, 2)

    # 4. Cotisations sociales
    cotisations = calculer_cotisations(total_cnss_base, baremes_cotisation)
    total_cotisations = round(sum(cotisations.values()), 2)
    
    # 5. Salaire net imposable
    cotisations_deductibles = (
        cotisations.get("CNSS", 0) + 
        cotisations.get("AMO", 0)
    )
    salaire_net_imposable = round(salaire_brut - cotisations_deductibles, 2)
    
    # 6. IR
    ir = calculer_ir(salaire_net_imposable, tranches_ir, parametres_legaux, employe.get("nb_personnes_a_charge", 0))
    
    # 7. Net à payer
    net_a_payer = round(salaire_brut - total_cotisations - ir, 2)
    
    total_retenues = round(total_cotisations + ir, 2)
    
    return {
        "salaire_base": salaire_base,
        "anciennete_annees": anciennete,
        "lignes_gains": lignes_gains,
        "total_gains": total_gains,
        "salaire_brut": salaire_brut,
        "cotisations": cotisations,
        "total_cotisations": total_cotisations,
        "cotisations_deductibles": cotisations_deductibles,
        "salaire_net_imposable": salaire_net_imposable,
        "total_ir": ir,
        "total_retenues": total_retenues,
        "salaire_net_a_payer": net_a_payer,
        "verification": {
            "brut": salaire_brut,
            "retenues": total_retenues,
            "net": net_a_payer,
            "somme": round(net_a_payer + total_retenues, 2),
            "est_coherent": round(net_a_payer + total_retenues, 2) == round(salaire_brut, 2)
        }
    }


# ============================================================
# EXEMPLE D'UTILISATION (donnees fictives, sans base de donnees)
# ============================================================
if __name__ == "__main__":
    employe_exemple = {
        "salaire_base": 8000,
        "date_embauche": "2019-03-01",  # ~7 ans d'anciennete en 2026
        "nb_personnes_a_charge": 2,
    }

    prime_anciennete = {
        "element": {
            "libelle": "Prime d'ancienneté",
            "mode_calcul": "bareme_anciennete",
            "valeur": None,
            "plafond_exoneration": None,
            "soumis_cnss": 1,
            "soumis_ir": 1,
        },
        "paliers": [
            {"annees_min": 2, "annees_max": 5, "taux": 5},
            {"annees_min": 5, "annees_max": 12, "taux": 10},
            {"annees_min": 12, "annees_max": 20, "taux": 15},
        ],
    }

    ind_transport = {
        "element": {
            "libelle": "Indemnité de transport",
            "mode_calcul": "montant_fixe",
            "valeur": 500,
            "plafond_exoneration": 500,
            "soumis_cnss": 0,
            "soumis_ir": 0,
        },
        "paliers": None,
    }

    baremes = [
        {"code": "CNSS", "taux_salarial": 4.48, "plafond_mensuel": 6000},
        {"code": "AMO", "taux_salarial": 2.26, "plafond_mensuel": None},
    ]

    tranches = [
        {"seuil_bas": 0, "seuil_haut": 40000, "taux": 0, "somme_a_deduire": 0},
        {"seuil_bas": 40001, "seuil_haut": 60000, "taux": 10, "somme_a_deduire": 4000},
        {"seuil_bas": 60001, "seuil_haut": 80000, "taux": 20, "somme_a_deduire": 10000},
        {"seuil_bas": 80001, "seuil_haut": 100000, "taux": 30, "somme_a_deduire": 18000},
        {"seuil_bas": 100001, "seuil_haut": 180000, "taux": 34, "somme_a_deduire": 22000},
        {"seuil_bas": 180001, "seuil_haut": None, "taux": 37, "somme_a_deduire": 29200},
    ]

    parametres_legaux = {
        "ABATTEMENT_SEUIL": 6500,
        "ABATTEMENT_TAUX_BAS": 35,
        "ABATTEMENT_TAUX_HAUT": 25,
        "CHARGE_FAMILLE_MONTANT": 50,
        "CHARGE_FAMILLE_PLAFOND": 300,
    }

    resultat = calculer_bulletin(
        employe_exemple,
        [prime_anciennete, ind_transport],
        baremes,
        tranches,
        parametres_legaux,
    )

    print("--- BULLETIN DE PAIE (exemple) ---")
    for k, v in resultat.items():
        print(f"{k}: {v}")


