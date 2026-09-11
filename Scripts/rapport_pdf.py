#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rapport_pdf.py
Ligue de Crible «Double-SKUNK» — Génération du rapport PDF de soirée
--------------------------------------------------------------
Module partagé, utilisé par :
  - double_skunk_import.py (génère le rapport automatiquement à la fin de
    chaque import)
  - generer_rapport.py (script séparé, demande une date de soirée et sort
    le PDF correspondant)

Le rapport a 4 pages :
  Page 1 — Stats de LA SOIRÉE : joueurs actifs, triés par moyenne de la
           soirée décroissante.
  Page 2 — Stats de LA SAISON (à ce jour) : joueurs actifs, triés par
           moyenne de saison décroissante.
  Page 3 — Résumé de la soirée courante : meneurs (skunks perdus/gagnés,
           défaites/victoires, total et consécutifs), moyennes basse/haute
           de la soirée, événements (mains rares), plus beau skunk.
  Page 4 — Stats de saison : top 8 des plus bas skunks de la saison,
           records de soirée (plus/moins de skunks, basse/haute moyenne
           générale), anniversaires du mois courant.

Seuls les joueurs actifs (profiles.actif = 1 dans double_skunk_ligue.db)
sont inclus, même s'ils ont joué cette soirée-là.
"""

import os
import sqlite3
import unicodedata
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# DejaVu Sans est nécessaire pour afficher ☹ / ☺ (Helvetica standard ne les
# supporte pas). Enregistrement silencieux — si les fichiers sont absents
# (autre machine que celle de développement), on retombe sur Helvetica.
try:
    pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
    POLICE_EMOJI = "DejaVuSans-Bold"
except Exception:
    POLICE_EMOJI = "Helvetica-Bold"

PATH_PROJECT = "/home/charles-ubuntu/Crible/Automation/"
DB_DIR = f"{PATH_PROJECT}DB"

DB_SOIREE = os.path.join(DB_DIR, "double_skunk_soiree.db")
DB_SAISON = os.path.join(DB_DIR, "double_skunk_saison.db")
DB_LIGUE  = os.path.join(DB_DIR, "double_skunk_ligue.db")

RAPPORTS_DIR = os.path.join(PATH_PROJECT, "Rapports")

EDITION_SAISON = "57 ième"  # édition de la saison en cours — codée en dur, à ajuster chaque nouvelle saison

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]

VISAGE_TRISTE = "\u2639"   # ☹
VISAGE_CONTENT = "\u263A"  # ☺


def formater_date_longue(date_iso):
    """'2026-07-04' -> 'vendredi 4 juillet 2026'"""
    d = datetime.strptime(date_iso, "%Y-%m-%d")
    return f"{JOURS_FR[d.weekday()]} {d.day} {MOIS_FR[d.month - 1]} {d.year}"


def formater_date_courte(date_iso):
    """'2026-07-04' -> '4 juillet 2026'"""
    d = datetime.strptime(date_iso, "%Y-%m-%d")
    return f"{d.day} {MOIS_FR[d.month - 1]} {d.year}"

COULEUR_ENTETE = colors.HexColor("#2c3e50")
COULEUR_LIGNE_ALT = colors.HexColor("#f0f2f5")


# ──────────────────────────────────────────────
# ACCÈS AUX DONNÉES
# ──────────────────────────────────────────────
def charger_joueurs_actifs():
    """Retourne {surnom: 'Prenom Nom'} pour les joueurs actifs."""
    conn = sqlite3.connect(DB_LIGUE)
    actifs = {}
    for surnom, prenom, nom in conn.execute(
        "SELECT surnom, prenom, nom FROM profiles WHERE actif = 1"
    ):
        actifs[surnom] = f"{prenom or surnom} {nom or ''}".strip()
    conn.close()
    return actifs


def trouver_soiree_par_date(date_soiree):
    """Retourne (id, soiree_num, soiree_vie_num, date, endroit, saison) pour
    la soirée correspondant à cette date, ou None si introuvable."""
    conn = sqlite3.connect(DB_SOIREE)
    row = conn.execute(
        "SELECT id, soiree_num, soiree_vie_num, date, endroit, saison FROM soirees WHERE date = ? ORDER BY id DESC LIMIT 1",
        (date_soiree,)
    ).fetchone()
    conn.close()
    return row


def charger_stats_soiree(soiree_id, joueurs_actifs):
    """Retourne une liste de lignes (triées par moyenne desc) pour les
    joueurs actifs ayant joué cette soirée-là."""
    conn = sqlite3.connect(DB_SOIREE)
    lignes = []
    for row in conn.execute("""
        SELECT surnom, points_tot, nbr_parties, moyenne, parties_g, parties_p,
               skunks_g, skunks_p, dbl_skunks_g, dbl_skunks_p
        FROM stats_joueurs WHERE soiree_id = ?
    """, (soiree_id,)):
        surnom = row[0]
        if surnom not in joueurs_actifs:
            continue
        lignes.append({
            "surnom": surnom, "nom_complet": joueurs_actifs[surnom],
            "points": row[1], "parties": row[2], "moyenne": row[3],
            "victoires": row[4], "defaites": row[5],
            "skunks_g": row[6], "skunks_p": row[7],
            "dbl_skunks_g": row[8], "dbl_skunks_p": row[9],
        })
    conn.close()
    lignes.sort(key=lambda x: x["moyenne"], reverse=True)
    return lignes


def charger_stats_saison(joueurs_actifs):
    """Retourne une liste de lignes (triées par moyenne de saison desc)
    pour les joueurs actifs."""
    conn = sqlite3.connect(DB_SAISON)
    lignes = []
    for row in conn.execute("""
        SELECT surnom, total_points, parties_jouees, soirees,
               parties_g, parties_p, skunks_g, skunks_p, dbl_skunks_g, dbl_skunks_p
        FROM stats_joueurs
    """):
        surnom, points, parties, soirees, parties_g, parties_p, skunks_g, skunks_p, dbl_skunks_g, dbl_skunks_p = row
        if surnom not in joueurs_actifs or not parties:
            continue
        lignes.append({
            "surnom": surnom, "nom_complet": joueurs_actifs[surnom],
            "points": points, "parties": parties, "soirees": soirees,
            "moyenne": round(points / parties, 2),
            "victoires": parties_g, "defaites": parties_p,
            "skunks_g": skunks_g, "skunks_p": skunks_p,
            "dbl_skunks_g": dbl_skunks_g, "dbl_skunks_p": dbl_skunks_p,
        })
    conn.close()
    lignes.sort(key=lambda x: x["moyenne"], reverse=True)
    return lignes


def charger_resume_soiree(soiree_id):
    """Retourne la ligne stats_soiree (meneurs de la soirée) sous forme de
    dict, ou None si absente."""
    conn = sqlite3.connect(DB_SOIREE)
    champs = ["skunks_perdus_nbr", "skunks_perdus_surnoms",
              "skunks_perdus_cons_nbr", "skunks_perdus_cons_surnoms",
              "skunks_gagnes_nbr", "skunks_gagnes_surnoms",
              "skunks_gagnes_cons_nbr", "skunks_gagnes_cons_surnoms",
              "defaites_nbr", "defaites_surnoms",
              "defaites_cons_nbr", "defaites_cons_surnoms",
              "victoires_nbr", "victoires_surnoms",
              "victoires_cons_nbr", "victoires_cons_surnoms",
              "basse_moy_nbr", "basse_moy_surnom",
              "haute_moy_nbr", "haute_moy_surnom",
              "evenements", "beau_skunk_soiree", "beau_skunk_soiree_par"]
    row = conn.execute(f"SELECT {', '.join(champs)} FROM stats_soiree WHERE soiree_id = ?", (soiree_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(zip(champs, row))


def charger_top8_skunks_saison(saison):
    """Retourne les 8 plus bas skunks de la saison (rang 1-8)."""
    conn = sqlite3.connect(DB_SAISON)
    lignes = [
        {"rang": r[0], "nbr": r[1], "date": r[2], "perdus_par": r[3], "gagnes_par": r[4]}
        for r in conn.execute("""
            SELECT rang, nbr, date, perdus_par, gagnes_par
            FROM plus_bas_skunks_saison WHERE saison = ? ORDER BY rang
        """, (saison,))
    ]
    conn.close()
    return lignes


def charger_records_saison(saison):
    """Retourne la dernière ligne stats_saison (records à jour) pour cette
    saison, sous forme de dict, ou None si absente."""
    conn = sqlite3.connect(DB_SAISON)
    champs = ["plus_de_skunks_nbr", "plus_de_skunks_text", "plus_de_skunks_date",
              "moins_de_skunks_nbr", "moins_de_skunks_text", "moins_de_skunks_date",
              "basse_moy_soiree_nbr", "basse_moy_soiree_text", "basse_moy_date",
              "haute_moy_soiree_nbr", "haute_moy_soiree_text", "haute_moy_date"]
    row = conn.execute(f"""
        SELECT {', '.join(champs)} FROM stats_saison
        WHERE saison = ? ORDER BY id DESC LIMIT 1
    """, (saison,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(zip(champs, row))


MOIS_ABBR_FR = {
    "janv": 1, "jan": 1,
    "fevr": 2, "fev": 2,
    "mars": 3, "mar": 3,
    "avr": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7, "jul": 7,
    "aout": 8,
    "sept": 9, "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _parser_date_naissance(naissance):
    """Parse une date de naissance stockée en 'D mois' (ex. '3 oct',
    '20 dec', sans année) OU en ISO 'YYYY-MM-DD'. Retourne (jour, mois)
    ou None si non reconnaissable."""
    naissance = (naissance or "").strip()
    if not naissance:
        return None

    # Format ISO éventuel
    try:
        d = datetime.strptime(naissance, "%Y-%m-%d")
        return d.day, d.month
    except ValueError:
        pass

    # Format 'D mois' (ex. '3 oct', '26 août')
    parties = naissance.split()
    if len(parties) != 2:
        return None
    jour_txt, mois_txt = parties
    try:
        jour = int(jour_txt)
    except ValueError:
        return None

    mois_norm = unicodedata.normalize("NFKD", mois_txt.lower()).encode("ascii", "ignore").decode()
    for abbr in sorted(MOIS_ABBR_FR, key=len, reverse=True):
        if mois_norm.startswith(abbr):
            return jour, MOIS_ABBR_FR[abbr]
    return None


def charger_anniversaires_du_mois(mois=None):
    """Retourne les profils actifs dont l'anniversaire tombe dans le mois
    donné (mois courant par défaut), triés par jour."""
    if mois is None:
        mois = datetime.now().month
    conn = sqlite3.connect(DB_LIGUE)
    resultats = []
    for prenom, nom, naissance in conn.execute(
        "SELECT prenom, nom, naissance FROM profiles WHERE actif = 1 AND naissance IS NOT NULL AND naissance != ''"
    ):
        parsed = _parser_date_naissance(naissance)
        if parsed is None:
            continue
        jour, mois_naissance = parsed
        if mois_naissance == mois:
            resultats.append({"nom_complet": f"{prenom or ''} {nom or ''}".strip(), "jour": jour})
    conn.close()
    resultats.sort(key=lambda x: x["jour"])
    return resultats


def _date_pour_soiree_id(sid):
    """Retourne la date (str) de la soirée dont l'id (double_skunk_soiree.db)
    est sid, ou None."""
    if sid is None:
        return None
    conn = sqlite3.connect(DB_SOIREE)
    row = conn.execute("SELECT date FROM soirees WHERE id = ?", (sid,)).fetchone()
    conn.close()
    return row[0] if row else None


def charger_finances_soiree(soiree_id):
    """Retourne (ligne_actuelle, date_precedente) où ligne_actuelle est un
    dict des finances pour cette soirée (ou None si absente), et
    date_precedente la date de la soirée précédente ayant une ligne finances
    (ou None si c'est la première)."""
    conn = sqlite3.connect(DB_LIGUE)
    champs = ["id", "id_soiree", "en_caisse_départ", "en_caisse_fin", "nbr_presences",
              "montant_presences", "hote_montant", "fond_montant", "nbr_skunks",
              "montant_skunks", "ajout_fond", "montant_depenses", "text_depenses"]
    rows = conn.execute(f"SELECT {', '.join(champs)} FROM finances ORDER BY id").fetchall()
    conn.close()

    actuelle = None
    precedente_id_soiree = None
    for i, r in enumerate(rows):
        d = dict(zip(champs, r))
        if d["id_soiree"] == soiree_id:
            actuelle = d
            if i > 0:
                precedente_id_soiree = dict(zip(champs, rows[i - 1]))["id_soiree"]
            break

    date_precedente = _date_pour_soiree_id(precedente_id_soiree)
    return actuelle, date_precedente


# ──────────────────────────────────────────────
# CONSTRUCTION DU PDF
# ──────────────────────────────────────────────
def _table_style(nb_lignes, ligne_debut_absents=None, ligne_total=None, compact=False):
    padding = 2 if compact else 5
    taille_entete = 8 if compact else 10
    taille_corps = 7.5 if compact else 9
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), COULEUR_ENTETE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), taille_entete),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), taille_corps),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]
    for i in range(1, nb_lignes + 1):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), COULEUR_LIGNE_ALT))
    if ligne_debut_absents is not None:
        style.append(("TEXTCOLOR", (0, ligne_debut_absents), (-1, nb_lignes), colors.HexColor("#888888")))
        style.append(("FONTNAME", (0, ligne_debut_absents), (-1, nb_lignes), "Helvetica-Oblique"))
    if ligne_total is not None:
        style.append(("FONTNAME", (0, ligne_total), (-1, ligne_total), "Helvetica-Bold"))
        style.append(("TEXTCOLOR", (0, ligne_total), (-1, ligne_total), colors.black))
        style.append(("LINEABOVE", (0, ligne_total), (-1, ligne_total), 1, colors.HexColor("#333333")))
        style.append(("BACKGROUND", (0, ligne_total), (-1, ligne_total), colors.white))
    return TableStyle(style)


def trouver_absents(joueurs_actifs, lignes):
    """Retourne la liste (triée alphabétiquement) des joueurs actifs qui
    n'ont pas de statistiques pour cette soirée (absents)."""
    presents = {l["surnom"] for l in lignes}
    absents = [
        {"surnom": surnom, "nom_complet": nom_complet}
        for surnom, nom_complet in joueurs_actifs.items() if surnom not in presents
    ]
    absents.sort(key=lambda x: x["nom_complet"])
    return absents


def _page_soiree(story, styles, soiree_info, lignes, absents):
    _id, soiree_num, soiree_vie_num, date, endroit, saison = soiree_info

    story.append(Paragraph('LIGUE DE CRIB "DOUBLE-SKUNK"', styles["TitreLigue"]))
    story.append(Paragraph(
        f"({EDITION_SAISON} saison - {soiree_vie_num} ième soirée)",
        styles["SousTitreCentre"]
    ))
    story.append(Paragraph(
        f"Rencontre #{soiree_num} du {formater_date_longue(date)} chez {endroit}  Saison {saison}",
        styles["SousTitreCentre"]
    ))
    story.append(Spacer(1, 16))

    if not lignes:
        story.append(Paragraph("Aucun joueur actif n'a de statistiques pour cette soirée.", styles["Normal"]))
        return

    entetes = ["Rang", "Joueur", "Points", "Parties", "Moyenne", "V", "D", "Sk. G", "Sk. P", "DSk. G", "DSk. P"]
    data = [entetes]

    for rang, l in enumerate(lignes, start=1):
        data.append([
            str(rang), l["nom_complet"], str(l["points"]), str(l["parties"]), f"{l['moyenne']:.2f}",
            str(l["victoires"]), str(l["defaites"]),
            str(l["skunks_g"]), str(l["skunks_p"]),
            str(l["dbl_skunks_g"]), str(l["dbl_skunks_p"]),
        ])

    ligne_debut_absents = len(data) if absents else None
    for a in absents:
        data.append(["", f"{a['nom_complet']} (absent)", "0", "0", "0.00", "0", "0", "0", "0", "0", "0"])

    # Ligne de total : sommes pour toutes les colonnes sauf Moyenne, qui
    # redonne la moyenne de tous les joueurs présents (absents exclus)
    total_points = sum(l["points"] for l in lignes)
    total_parties = sum(l["parties"] for l in lignes)
    total_victoires = sum(l["victoires"] for l in lignes)
    total_defaites = sum(l["defaites"] for l in lignes)
    total_skunks_g = sum(l["skunks_g"] for l in lignes)
    total_skunks_p = sum(l["skunks_p"] for l in lignes)
    total_dsk_g = sum(l["dbl_skunks_g"] for l in lignes)
    total_dsk_p = sum(l["dbl_skunks_p"] for l in lignes)
    moyenne_generale = round(total_points / total_parties, 2) if total_parties else 0

    ligne_total = len(data)
    data.append([
        "", "TOTAL", str(total_points), str(total_parties), f"{moyenne_generale:.2f}",
        str(total_victoires), str(total_defaites),
        str(total_skunks_g), str(total_skunks_p),
        str(total_dsk_g), str(total_dsk_p),
    ])

    largeurs = [1.1*cm, 4.3*cm, 1.7*cm, 1.7*cm, 1.9*cm, 1.1*cm, 1.1*cm, 1.5*cm, 1.5*cm, 1.7*cm, 1.7*cm]
    table = Table(data, colWidths=largeurs, repeatRows=1)
    table.setStyle(_table_style(len(data) - 1, ligne_debut_absents, ligne_total))
    story.append(table)


def _page_saison(story, styles, lignes, absents, saison_label, date_reference):
    story.append(Paragraph('LIGUE DE CRIB "DOUBLE-SKUNK"', styles["TitreLigue"]))
    story.append(Paragraph(
        f"Moyennes cumulatives de la saison {saison_label} en date du {formater_date_courte(date_reference)}",
        styles["SousTitreCentre"]
    ))
    story.append(Spacer(1, 16))

    if not lignes:
        story.append(Paragraph("Aucun joueur actif n'a de statistiques pour cette saison.", styles["Normal"]))
        return

    entetes = ["Rang", "Joueur", "Points", "Parties", "Moyenne", "Soirées",
               "V", "D", "Sk. G", "Sk. P", "DSk. G", "DSk. P"]
    data = [entetes]

    for rang, l in enumerate(lignes, start=1):
        data.append([
            str(rang), l["nom_complet"], str(l["points"]), str(l["parties"]), f"{l['moyenne']:.2f}",
            str(l["soirees"]), str(l["victoires"]), str(l["defaites"]),
            str(l["skunks_g"]), str(l["skunks_p"]), str(l["dbl_skunks_g"]), str(l["dbl_skunks_p"]),
        ])

    ligne_debut_absents = len(data) if absents else None
    for a in absents:
        data.append(["", f"{a['nom_complet']} (absent)", "0", "0", "0.00", "0", "0", "0", "0", "0", "0", "0"])

    # Ligne de total : sommes pour toutes les colonnes sauf Moyenne, qui
    # redonne la moyenne de tous les joueurs actifs ayant joué (absents exclus)
    total_points = sum(l["points"] for l in lignes)
    total_parties = sum(l["parties"] for l in lignes)
    total_soirees = sum(l["soirees"] for l in lignes)
    total_victoires = sum(l["victoires"] for l in lignes)
    total_defaites = sum(l["defaites"] for l in lignes)
    total_skunks_g = sum(l["skunks_g"] for l in lignes)
    total_skunks_p = sum(l["skunks_p"] for l in lignes)
    total_dsk_g = sum(l["dbl_skunks_g"] for l in lignes)
    total_dsk_p = sum(l["dbl_skunks_p"] for l in lignes)
    moyenne_generale = round(total_points / total_parties, 2) if total_parties else 0

    ligne_total = len(data)
    data.append([
        "", "TOTAL", str(total_points), str(total_parties), f"{moyenne_generale:.2f}", str(total_soirees),
        str(total_victoires), str(total_defaites),
        str(total_skunks_g), str(total_skunks_p), str(total_dsk_g), str(total_dsk_p),
    ])

    largeurs = [1.1*cm, 4*cm, 1.7*cm, 1.7*cm, 1.9*cm, 1.7*cm, 1.1*cm, 1.1*cm, 1.5*cm, 1.5*cm, 1.7*cm, 1.7*cm]
    table = Table(data, colWidths=largeurs, repeatRows=1)
    table.setStyle(_table_style(len(data) - 1, ligne_debut_absents, ligne_total))
    story.append(table)


def _ligne_resume(surnoms_bruts):
    """'Carole,Denis' -> 'Carole, Denis' (lisible)."""
    if not surnoms_bruts:
        return "—"
    return ", ".join(s.strip() for s in surnoms_bruts.split(","))


def _page_resume(story, styles, soiree_info, resume):
    _id, soiree_num, soiree_vie_num, date, endroit, saison = soiree_info

    story.append(Paragraph('LIGUE DE CRIB "DOUBLE-SKUNK"', styles["TitreLigue"]))
    story.append(Paragraph(
        f"Résumé de la soirée #{soiree_num} — {formater_date_courte(date)}",
        styles["SousTitreCentre"]
    ))
    story.append(Spacer(1, 16))

    if resume is None:
        story.append(Paragraph("Aucun résumé disponible pour cette soirée.", styles["Normal"]))
        return

    lignes = [
        ("Plus de skunks perdus", str(resume["skunks_perdus_nbr"]), _ligne_resume(resume["skunks_perdus_surnoms"])),
        ("Plus de skunks perdus consécutivement", str(resume["skunks_perdus_cons_nbr"]), _ligne_resume(resume["skunks_perdus_cons_surnoms"])),
        ("Plus de skunks gagnés", str(resume["skunks_gagnes_nbr"]), _ligne_resume(resume["skunks_gagnes_surnoms"])),
        ("Plus de skunks gagnés consécutivement", str(resume["skunks_gagnes_cons_nbr"]), _ligne_resume(resume["skunks_gagnes_cons_surnoms"])),
        ("Plus de défaites", str(resume["defaites_nbr"]), _ligne_resume(resume["defaites_surnoms"])),
        ("Plus de défaites consécutives", str(resume["defaites_cons_nbr"]), _ligne_resume(resume["defaites_cons_surnoms"])),
        ("Plus de victoires", str(resume["victoires_nbr"]), _ligne_resume(resume["victoires_surnoms"])),
        ("Plus de victoires consécutives", str(resume["victoires_cons_nbr"]), _ligne_resume(resume["victoires_cons_surnoms"])),
        ("Plus basse moyenne de la soirée", f"{resume['basse_moy_nbr']:.2f}" if resume["basse_moy_nbr"] is not None else "—", resume["basse_moy_surnom"] or "—"),
        ("Plus haute moyenne de la soirée", f"{resume['haute_moy_nbr']:.2f}" if resume["haute_moy_nbr"] is not None else "—", resume["haute_moy_surnom"] or "—"),
        ("Plus beau skunk de la soirée", str(resume["beau_skunk_soiree"]) if resume["beau_skunk_soiree"] else "—", resume["beau_skunk_soiree_par"] or "—"),
    ]

    data = [["Statistique", "Nombre", "Détails"]]
    for label, nbr, details in lignes:
        data.append([label, nbr, details])

    largeurs = [6.5*cm, 2*cm, 8*cm]
    table = Table(data, colWidths=largeurs, repeatRows=1)
    table.setStyle(_table_style(len(lignes)))
    story.append(table)

    story.append(Spacer(1, 20))
    story.append(Paragraph("Événements de la soirée (mains rares, etc.)", styles["SousTitre"]))
    story.append(Spacer(1, 6))
    evenements = resume["evenements"]
    if evenements:
        for evt in evenements.split(";"):
            evt = evt.strip()
            if evt:
                story.append(Paragraph(f"•  {evt}", styles["Normal"]))
    else:
        story.append(Paragraph("Aucun événement rapporté pour cette soirée.", styles["Normal"]))


def _page_stats_saison(story, styles, saison_label, top8, records, anniversaires, finances, date_precedente, date_actuelle):
    story.append(Paragraph('LIGUE DE CRIB "DOUBLE-SKUNK"', styles["TitreLigue"]))
    story.append(Paragraph(f"Statistiques de la saison {saison_label}", styles["SousTitreCentre"]))
    story.append(Spacer(1, 8))

    # ── Top 8 des plus bas skunks de la saison ──
    story.append(Paragraph("Les 8 plus beaux skunks de la saison", styles["SousTitrePage4"]))
    story.append(Spacer(1, 3))

    entete_perdus = f"{VISAGE_TRISTE} Perdus par {VISAGE_TRISTE}"
    entete_gagnes = f"{VISAGE_CONTENT} Gagnés par {VISAGE_CONTENT}"
    data = [["Rang", "Points", "Date", entete_perdus, entete_gagnes]]
    for l in top8:
        data.append([str(l["rang"]), str(l["nbr"]), formater_date_courte(l["date"]) if l["date"] else "—",
                     l["perdus_par"] or "—", l["gagnes_par"] or "—"])
    if len(data) == 1:
        data.append(["—", "—", "—", "Aucune donnée", "Aucune donnée"])

    largeurs = [1.3*cm, 1.3*cm, 3*cm, 4.2*cm, 4.2*cm]
    table = Table(data, colWidths=largeurs, repeatRows=1)
    table.setStyle(_table_style(len(data) - 1, compact=True))
    table.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), POLICE_EMOJI), ("FONTSIZE", (0, 0), (-1, 0), 8)]))
    story.append(table)
    story.append(Spacer(1, 10))

    # ── Records de soirée de la saison ──
    story.append(Paragraph("Records de soirée de la saison", styles["SousTitrePage4"]))
    story.append(Spacer(1, 3))

    if records is None:
        story.append(Paragraph("Aucun record disponible pour cette saison.", styles["Normal"]))
    else:
        lignes = [
            ("Plus de skunks pour une soirée", str(records["plus_de_skunks_nbr"]),
             records["plus_de_skunks_text"] or "—", records["plus_de_skunks_date"]),
            ("Moins de skunks pour une soirée", str(records["moins_de_skunks_nbr"]),
             records["moins_de_skunks_text"] or "—", records["moins_de_skunks_date"]),
            ("Plus basse moyenne générale pour une soirée", f"{records['basse_moy_soiree_nbr']:.2f}" if records["basse_moy_soiree_nbr"] is not None else "—",
             records["basse_moy_soiree_text"] or "—", records["basse_moy_date"]),
            ("Plus haute moyenne générale pour une soirée", f"{records['haute_moy_soiree_nbr']:.2f}" if records["haute_moy_soiree_nbr"] is not None else "—",
             records["haute_moy_soiree_text"] or "—", records["haute_moy_date"]),
        ]
        style_cell = ParagraphStyle("CelluleTable", parent=styles["Normal"], fontSize=7.5, leading=9)
        data = [["Statistique", "Total", "Détails", "Date"]]
        for label, total, details, date_rec in lignes:
            dates_affichees = ", ".join(formater_date_courte(d) for d in date_rec.split(",")) if date_rec else "—"
            data.append([Paragraph(label, style_cell), total, Paragraph(details, style_cell), dates_affichees])

        largeurs = [5.5*cm, 1.8*cm, 5.5*cm, 3.5*cm]
        table = Table(data, colWidths=largeurs, repeatRows=1)
        table.setStyle(_table_style(len(lignes), compact=True))
        story.append(table)

    story.append(Spacer(1, 10))

    # ── Recettes et dépenses de la saison ──
    story.append(Paragraph(f"Recettes et dépenses de la {EDITION_SAISON} saison", styles["SousTitrePage4"]))
    story.append(Paragraph(f"au {formater_date_courte(date_actuelle)}", styles["Meta"]))
    story.append(Spacer(1, 3))

    if finances is None:
        story.append(Paragraph("Aucune donnée financière pour cette soirée.", styles["Normal"]))
    else:
        style_entete = ParagraphStyle("EnteteFinances", parent=styles["Normal"],
                                       fontSize=7, leading=8.5, textColor=colors.white, alignment=1)
        libelle_prec = f"Encaisse au {formater_date_courte(date_precedente)}" if date_precedente else "Encaisse au départ"
        libelle_actuel = f"En caisse au {formater_date_courte(date_actuelle)}"
        libelle_depenses = f"Dépenses ({finances['text_depenses']})"

        entetes = [Paragraph(t, style_entete) for t in [
            libelle_prec, "Présences", "Hôte", "Fond", "Skunks", "Ajouté au fond",
            libelle_depenses, libelle_actuel,
        ]]

        def _argent(v):
            return f"{v:.2f} $"

        valeurs = [
            _argent(finances["en_caisse_départ"]), _argent(finances["montant_presences"]),
            _argent(finances["hote_montant"]), _argent(finances["fond_montant"]),
            _argent(finances["montant_skunks"]), _argent(finances["ajout_fond"]),
            _argent(finances["montant_depenses"]), _argent(finances["en_caisse_fin"]),
        ]

        data = [entetes, valeurs]
        largeurs = [2.2*cm] * 8
        table = Table(data, colWidths=largeurs, repeatRows=1)
        table.setStyle(_table_style(1, compact=True))
        story.append(table)

    story.append(Spacer(1, 10))

    # ── Anniversaires du mois courant (2 paires par ligne pour limiter la hauteur) ──
    mois_nom = MOIS_FR[datetime.now().month - 1].capitalize()
    story.append(Paragraph(f"Anniversaires de {mois_nom}", styles["SousTitrePage4"]))
    story.append(Spacer(1, 3))
    if anniversaires:
        entetes = ["Joueur", "Jour", "Joueur", "Jour"]
        data = [entetes]
        for i in range(0, len(anniversaires), 2):
            gauche = anniversaires[i]
            droite = anniversaires[i + 1] if i + 1 < len(anniversaires) else None
            data.append([
                gauche["nom_complet"], str(gauche["jour"]),
                droite["nom_complet"] if droite else "", str(droite["jour"]) if droite else "",
            ])
        largeurs = [5*cm, 1.7*cm, 5*cm, 1.7*cm]
        table = Table(data, colWidths=largeurs, repeatRows=1)
        table.setStyle(_table_style(len(data) - 1, compact=True))
        story.append(table)
    else:
        story.append(Paragraph("Aucun anniversaire ce mois-ci.", styles["Normal"]))


def generer_rapport(date_soiree, chemin_sortie=None):
    """Génère le PDF 2 pages (soirée + saison) pour la soirée correspondant
    à date_soiree ('YYYY-MM-DD'). Retourne le chemin du PDF créé, ou None
    si la soirée est introuvable."""
    soiree_info = trouver_soiree_par_date(date_soiree)
    if soiree_info is None:
        print(f"  ⚠️  Aucune soirée trouvée pour la date {date_soiree}.")
        return None

    _id, soiree_num, soiree_vie_num, date, endroit, saison = soiree_info
    joueurs_actifs = charger_joueurs_actifs()
    lignes_soiree = charger_stats_soiree(_id, joueurs_actifs)
    absents_soiree = trouver_absents(joueurs_actifs, lignes_soiree)
    lignes_saison = charger_stats_saison(joueurs_actifs)
    absents_saison = trouver_absents(joueurs_actifs, lignes_saison)
    resume_soiree = charger_resume_soiree(_id)
    top8_skunks = charger_top8_skunks_saison(saison)
    records_saison = charger_records_saison(saison)
    anniversaires = charger_anniversaires_du_mois()
    finances_soiree, date_finances_precedente = charger_finances_soiree(_id)

    os.makedirs(RAPPORTS_DIR, exist_ok=True)
    if chemin_sortie is None:
        chemin_sortie = os.path.join(RAPPORTS_DIR, f"rapport_soiree_{soiree_num}_{date}.pdf")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TitreLigue", parent=styles["Title"], fontSize=18, spaceAfter=2))
    styles.add(ParagraphStyle("SousTitre", parent=styles["Heading2"], fontSize=13, textColor=COULEUR_ENTETE))
    styles.add(ParagraphStyle("SousTitrePage4", parent=styles["Heading2"], fontSize=10.5,
                               textColor=COULEUR_ENTETE, spaceAfter=0, spaceBefore=0))
    styles.add(ParagraphStyle("SousTitreCentre", parent=styles["Heading2"], fontSize=12,
                               textColor=COULEUR_ENTETE, alignment=1))
    styles.add(ParagraphStyle("Meta", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#555555")))

    doc = SimpleDocTemplate(chemin_sortie, pagesize=letter,
                             topMargin=1.5*cm, bottomMargin=1.5*cm,
                             leftMargin=1.5*cm, rightMargin=1.5*cm)
    story = []
    _page_soiree(story, styles, soiree_info, lignes_soiree, absents_soiree)
    story.append(PageBreak())
    _page_saison(story, styles, lignes_saison, absents_saison, saison, date)
    story.append(PageBreak())
    _page_resume(story, styles, soiree_info, resume_soiree)
    story.append(PageBreak())
    _page_stats_saison(story, styles, saison, top8_skunks, records_saison, anniversaires,
                       finances_soiree, date_finances_precedente, date)

    doc.build(story)
    print(f"  📄 Rapport PDF généré → {chemin_sortie}")
    return chemin_sortie


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python rapport_pdf.py <YYYY-MM-DD>")
        sys.exit(1)
    generer_rapport(sys.argv[1])
