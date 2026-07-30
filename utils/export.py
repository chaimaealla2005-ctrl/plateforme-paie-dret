# utils/export.py
import csv
import io
from flask import Response
import pandas as pd
from datetime import datetime


def export_to_csv(data, headers, filename):
    """Exporte des données vers un fichier CSV"""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    
    writer.writerow(headers)
    
    for row in data:
        writer.writerow(row)
    
    response = Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8-sig'
    )
    response.headers['Content-Disposition'] = f'attachment; filename={filename}_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    
    return response


def export_to_excel(data, headers, filename, sheet_name='Donnees'):
    """Exporte des données vers un fichier Excel"""
    df = pd.DataFrame(data, columns=headers)
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    response = Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response.headers['Content-Disposition'] = f'attachment; filename={filename}_{datetime.now().strftime("%Y%m%d")}.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response


def _row_to_dict(row):
    """Convertit un sqlite3.Row en dictionnaire"""
    if hasattr(row, 'keys'):
        return {k: row[k] for k in row.keys()}
    return dict(row) if row else {}


def export_employes(employes):
    """Prépare les données des employés pour l'export"""
    headers = ['Matricule', 'Nom', 'Prénom', 'CIN', 'Poste', 'Grade', 
               'Salaire de base', 'Date d\'embauche', 'Société', 'Statut', 'Email', 'Téléphone']
    
    data = []
    for e in employes:
        row = _row_to_dict(e)
        data.append([
            row.get('matricule', ''),
            row.get('nom', ''),
            row.get('prenom', ''),
            row.get('cin', ''),
            row.get('poste', ''),
            row.get('grade', ''),
            row.get('salaire_base', 0),
            row.get('date_embauche', ''),
            row.get('raison_sociale', ''),
            'Actif' if row.get('actif', 1) == 1 else 'Inactif',
            row.get('email', ''),
            row.get('telephone', '')
        ])
    
    return headers, data


def export_bulletins(bulletins):
    """Prépare les données des bulletins pour l'export"""
    headers = ['Société', 'Employé', 'Matricule', 'Période', 
               'Salaire brut', 'CNSS', 'AMO', 'IR', 'Salaire net', 'Date génération']
    
    data = []
    for b in bulletins:
        row = _row_to_dict(b)
        
        prenom = row.get('prenom', '')
        nom = row.get('nom', '')
        nom_complet = f"{prenom} {nom}" if prenom or nom else ''
        
        data.append([
            row.get('raison_sociale', ''),
            nom_complet,
            row.get('matricule', ''),
            f"{row.get('mois', '')}/{row.get('annee', '')}",
            row.get('salaire_brut', 0),
            row.get('total_cnss', 0),
            row.get('total_amo', 0),
            row.get('total_ir', 0),
            row.get('salaire_net_a_payer', 0),
            row.get('date_generation', '')[:10] if row.get('date_generation') else ''
        ])
    
    return headers, data


def export_societes(societes):
    """Prépare les données des sociétés pour l'export"""
    headers = ['Raison sociale', 'ICE', 'Adresse', 'Employés', 'Utilisateurs', 'Statut']
    
    data = []
    for s in societes:
        row = _row_to_dict(s)
        data.append([
            row.get('raison_sociale', ''),
            row.get('ice', ''),
            row.get('adresse', ''),
            row.get('nb_employes', 0),
            row.get('nb_utilisateurs', 0),
            'Active' if row.get('actif', 1) == 1 else 'Inactive'
        ])
    
    return headers, data