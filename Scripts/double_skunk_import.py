#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
double_skunk_import.py
Ligue de Crible «Double-SKUNK» — Importation JSON vers SQLite
--------------------------------------------------------------
Usage:
    python double_skunk_import.py <fichier.json>

4 bases de données SQLite sont créées/mises à jour :
    double_skunk_ligue.db   — profils joueurs (prenom, nom, surnom, ...) + finances
    double_skunk_soiree.db  — données de la soirée importée
    double_skunk_saison.db  — cumul de la saison en cours
    double_skunk_a_vie.db   — cumul à vie (toutes saisons)

Référence croisée :
    La clé de jonction entre le profil et les autres DB est le SURNOM
    (nom utilisé pour désigner un joueur pendant les soirées).
    Les tables `presence`, `stats_joueurs` et `stats_a_vie_joueurs` stockent
    maintenant `surnom` (clé) + `prenom` et `nom` (copiés depuis
    double_skunk_ligue.db via une recherche sur le surnom, à chaque
    import — voir charger_lookup_profiles()).
"""

import sys
import json
import sqlite3
import os
from datetime import datetime

import rapport_pdf

PATH_PROJECT = "/home/charles-ubuntu/Crible/Automation/"

# ──────────────────────────────────────────────
# FICHIERS DE BASE DE DONNÉES
# ──────────────────────────────────────────────
DB_DIR = f"{PATH_PROJECT}DB"
os.makedirs(DB_DIR, exist_ok=True)

DB_SOIREE  = os.path.join(DB_DIR, "double_skunk_soiree.db")
DB_SAISON  = os.path.join(DB_DIR, "double_skunk_saison.db")
DB_A_VIE   = os.path.join(DB_DIR, "double_skunk_a_vie.db")
DB_LIGUE   = os.path.join(DB_DIR, "double_skunk_ligue.db")


# ──────────────────────────────────────────────
# CRÉATION DES TABLES
# ──────────────────────────────────────────────

def init_db_ligue(conn):
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            prenom          TEXT,
            nom             TEXT,
            surnom          TEXT,
            anciennete      INTEGER,
            date_entree     TEXT,
            naissance       TEXT,
            tel_maison      TEXT,
            cellulaire      TEXT,
            adresse         TEXT,
            courriel        TEXT,
            notes           TEXT,
            actif           INTEGER DEFAULT 1,
            derniere_maj    TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS finances (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            id_soiree           INTEGER,
            saison              TEXT,
            en_caisse_départ    REAL,
            en_caisse_fin       REAL,
            nbr_presences       INTEGER,
            montant_presences   REAL,
            hote_montant        REAL,
            fond_montant        REAL,
            nbr_skunks          INTEGER,
            montant_skunks      REAL,
            ajout_fond          REAL,
            montant_depenses    REAL,
            text_depenses       TEXT
        )
    """)
    conn.commit()


def init_db_soiree(conn):
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS soirees (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_num      INTEGER,
            soiree_vie_num  INTEGER,
            saison          TEXT,
            date            TEXT,
            endroit         TEXT,
            prochaine_chez  TEXT,
            prochaine_date  TEXT,
            importe_le      TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS parties (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_id   INTEGER,
            numero      INTEGER,
            joueur_a    TEXT,
            joueur_b    TEXT,
            points_1    INTEGER,
            points_2    INTEGER,
            joueur_c    TEXT,
            joueur_d    TEXT,
            FOREIGN KEY (soiree_id) REFERENCES soirees(id)
        )
    """)
    # Note: joueur_a/b/c/d contiennent déjà le surnom du joueur (clé de
    # référence vers profiles.surnom). Pas de prenom/nom dupliqués ici
    # pour éviter 8 colonnes supplémentaires sur une table à 4 joueurs
    # par ligne — la jonction se fait via surnom au besoin.

    c.execute("""
        CREATE TABLE IF NOT EXISTS presence (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_id   INTEGER,
            surnom      TEXT,
            prenom      TEXT,
            nom         TEXT,
            numero      TEXT,
            FOREIGN KEY (soiree_id) REFERENCES soirees(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS stats_joueurs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_id       INTEGER,
            surnom          TEXT,
            points_tot      INTEGER,
            nbr_parties     INTEGER,
            moyenne         REAL,
            parties_g       INTEGER,
            parties_p       INTEGER,
            skunks_g        INTEGER,
            skunks_p        INTEGER,
            dbl_skunks_g    INTEGER,
            dbl_skunks_p    INTEGER,
            FOREIGN KEY (soiree_id) REFERENCES soirees(id)
        )
    """)
    # Note: surnom fait référence à profiles.surnom (double_skunk_ligue.db).
    # Pas de FOREIGN KEY SQL pour ce lien : SQLite ne supporte pas les clés
    # étrangères entre fichiers de DB distincts — c'est une référence
    # documentaire, comme prenom/nom ailleurs dans le script.

    c.execute("""
        CREATE TABLE IF NOT EXISTS stats_soiree (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_id                   INTEGER,
            date                        TEXT,
            saison                      TEXT,
            skunks_perdus_nbr           INTEGER,
            skunks_perdus_surnoms       TEXT,
            skunks_perdus_cons_nbr      INTEGER,
            skunks_perdus_cons_surnoms  TEXT,
            skunks_gagnes_nbr           INTEGER,
            skunks_gagnes_surnoms       TEXT,
            skunks_gagnes_cons_nbr      INTEGER,
            skunks_gagnes_cons_surnoms  TEXT,
            defaites_nbr                INTEGER,
            defaites_surnoms            TEXT,
            defaites_cons_nbr           INTEGER,
            defaites_cons_surnoms       TEXT,
            victoires_nbr               INTEGER,
            victoires_surnoms           TEXT,
            victoires_cons_nbr          INTEGER,
            victoires_cons_surnoms      TEXT,
            basse_moy_nbr               REAL,
            basse_moy_surnom            TEXT,
            haute_moy_nbr               REAL,
            haute_moy_surnom            TEXT,
            evenements                  TEXT,
            beau_skunk_soiree           INTEGER,
            beau_skunk_soiree_par       TEXT,
            FOREIGN KEY (soiree_id) REFERENCES soirees(id)
        )
    """)

    conn.commit()


def init_db_saison(conn):
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS stats_joueurs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            surnom          TEXT UNIQUE,
            prenom          TEXT,
            nom             TEXT,
            parties_jouees  INTEGER DEFAULT 0,
            total_points    INTEGER DEFAULT 0,
            soirees         INTEGER DEFAULT 0,
            derniere_maj    TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS soirees_saison (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_num      INTEGER UNIQUE,
            saison          TEXT,
            date            TEXT,
            endroit         TEXT,
            nb_parties      INTEGER,
            nb_joueurs      INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS stats_saison (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            saison                  TEXT,
            plus_de_skunks_nbr      INTEGER,
            plus_de_skunks_text     TEXT,
            plus_de_skunks_date     TEXT,
            plus_de_skunks_soiree_num   INTEGER,
            moins_de_skunks_nbr     INTEGER,
            moins_de_skunks_text    TEXT,
            moins_de_skunks_date    TEXT,
            moins_de_skunks_soiree_num  INTEGER,
            basse_moy_soiree_nbr    REAL,
            basse_moy_soiree_text   TEXT,
            basse_moy_date          TEXT,
            basse_moy_soiree_num    INTEGER,
            haute_moy_soiree_nbr    REAL,
            haute_moy_soiree_text   TEXT,
            haute_moy_date          TEXT,
            haute_moy_soiree_num    INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS plus_bas_skunks_saison (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            saison      TEXT,
            soiree_num  INTEGER,
            rang        INTEGER,
            nbr         INTEGER,
            date        TEXT,
            perdus_par  TEXT,
            gagnes_par  TEXT
        )
    """)

    conn.commit()


def init_db_a_vie(conn):
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS stats_a_vie_joueurs (
            id                              INTEGER PRIMARY KEY AUTOINCREMENT,
            surnom                          TEXT UNIQUE,
            prenom                          TEXT,
            nom                             TEXT,
            points                          INTEGER DEFAULT 0,
            parties                         INTEGER DEFAULT 0,
            moy                             REAL,
            parties_gagnees                 INTEGER DEFAULT 0,
            parties_perdues                 INTEGER DEFAULT 0,
            sks_gagnes                      INTEGER DEFAULT 0,
            dsks_gagnes                     INTEGER DEFAULT 0,
            sks_perdus                      INTEGER DEFAULT 0,
            dsks_perdus                     INTEGER DEFAULT 0,
            plus_beau_skunk_perdu           INTEGER,
            plus_beau_skunk_perdu_text      TEXT,
            plus_beau_skunk_perdu_date      TEXT,
            plus_beau_skunk_gagne           INTEGER,
            plus_beau_skunk_gagne_text      TEXT,
            plus_beau_skunk_gagne_date      TEXT,
            plus_de_skunks_perdus           INTEGER,
            plus_de_skunks_perdus_text      TEXT,
            plus_de_skunks_perdus_date      TEXT,
            de_skunks_cons_perdus           INTEGER,
            de_skunks_cons_perdus_text      TEXT,
            de_skunks_cons_perdus_date      TEXT,
            plus_de_skunks_gagnes           INTEGER,
            plus_de_skunks_gagnes_text      TEXT,
            plus_de_skunks_gagnes_date      TEXT,
            de_skunks_cons_gagnes           INTEGER,
            de_skunks_cons_gagnes_text      TEXT,
            de_skunks_cons_gagnes_date      TEXT,
            plus_de_defaites                INTEGER,
            plus_de_defaites_text           TEXT,
            plus_de_defaites_date           TEXT,
            de_defaites_consec              INTEGER,
            de_defaites_consec_text         TEXT,
            de_defaites_consec_date         TEXT,
            plus_de_victoires               INTEGER,
            plus_de_victoires_text          TEXT,
            plus_de_victoires_date          TEXT,
            de_victoires_consec             INTEGER,
            de_victoires_consec_text        TEXT,
            de_victoires_consec_date        TEXT,
            plus_basse_moy_de_soiree        INTEGER,
            plus_basse_moy_de_soiree_text   TEXT,
            plus_basse_moy_de_soiree_date   TEXT,
            haute_moy_de_soiree             INTEGER,
            haute_moy_de_soiree_text        TEXT,
            haute_moy_de_soiree_date        TEXT,
            plus_basse_moy_de_saison        INTEGER,
            plus_basse_moy_de_saison_text   TEXT,
            plus_basse_moy_de_saison_date   TEXT,
            haute_moy_de_saison             INTEGER,
            haute_moy_de_saison_text        TEXT,
            haute_moy_de_saison_date        TEXT,
            derniere_maj                    TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS soirees_a_vie (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_num      INTEGER,
            soiree_vie_num  INTEGER UNIQUE,
            saison          TEXT,
            date            TEXT,
            endroit         TEXT,
            nb_parties      INTEGER,
            nb_joueurs      INTEGER
        )
    """)

    conn.commit()


# ──────────────────────────────────────────────
# RECHERCHE PROFIL (surnom -> prenom, nom)
# ──────────────────────────────────────────────
def charger_lookup_profiles():
    """Retourne {surnom: (prenom, nom)} depuis double_skunk_ligue.db"""
    lookup = {}
    conn = sqlite3.connect(DB_LIGUE)
    init_db_ligue(conn)
    c = conn.cursor()
    c.execute("SELECT surnom, prenom, nom FROM profiles WHERE surnom IS NOT NULL AND surnom != ''")
    for surnom, prenom, nom in c.fetchall():
        lookup[surnom] = (prenom, nom)
    conn.close()
    return lookup


# ──────────────────────────────────────────────
# CALCUL DES STATS DE LA SOIRÉE (par joueur)
# ──────────────────────────────────────────────
def _stat_vide():
    return {
        "points_tot": 0, "nbr_parties": 0,
        "parties_g": 0, "parties_p": 0,
        "skunks_g": 0, "skunks_p": 0,
        "dbl_skunks_g": 0, "dbl_skunks_p": 0,
    }


def calculer_stats_joueurs_soiree(parties):
    """Calcule, pour chaque surnom, les stats de la soirée à partir des parties.
    Victoire = 121 points ; skunk = adversaire à 90 pts ou moins ;
    double skunk = adversaire à 60 pts ou moins (un double skunk compte
    aussi comme un skunk)."""
    stats = {}

    for p in parties:
        pts1 = p.get("pts1", None)
        pts2 = p.get("pts2", None)
        pts1 = int(pts1) if pts1 not in (None, "") else None
        pts2 = int(pts2) if pts2 not in (None, "") else None
        if pts1 is None or pts2 is None:
            continue  # partie incomplète, ignorée dans les stats

        equipe1 = [j for j in [p.get("na", ""), p.get("nb", "")] if j]
        equipe2 = [j for j in [p.get("nc", ""), p.get("nd", "")] if j]

        for joueurs, mes_pts, pts_adv in ((equipe1, pts1, pts2), (equipe2, pts2, pts1)):
            for joueur in joueurs:
                s = stats.setdefault(joueur, _stat_vide())
                s["nbr_parties"] += 1
                s["points_tot"] += mes_pts
                if mes_pts == 121:
                    s["parties_g"] += 1
                    if pts_adv <= 90:
                        s["skunks_g"] += 1
                    if pts_adv <= 60:
                        s["dbl_skunks_g"] += 1
                else:
                    s["parties_p"] += 1
                    if mes_pts <= 90:
                        s["skunks_p"] += 1
                    if mes_pts <= 60:
                        s["dbl_skunks_p"] += 1

    return stats


# ──────────────────────────────────────────────
# MENEURS DE LA SOIRÉE (pour stats_soiree)
# ──────────────────────────────────────────────
def _trouver_meneurs(valeurs, seuil_min=1):
    """valeurs: {surnom: valeur}. Retourne (valeur_max, "surnom1,surnom2")
    pour le(s) surnom(s) à égalité au maximum. Si personne n'atteint
    seuil_min, retourne (0, "")."""
    if not valeurs:
        return 0, ""
    max_val = max(valeurs.values())
    if max_val < seuil_min:
        return 0, ""
    gagnants = sorted(s for s, v in valeurs.items() if v == max_val)
    return max_val, ",".join(gagnants)


def calculer_streak_max(parties, condition):
    """Retourne {surnom: plus long enchaînement consécutif} où condition(mes_pts, pts_adv, gagne)
    détermine si la partie compte pour l'enchaînement de ce joueur. Suit l'ordre des parties
    (numero) pour chaque joueur."""
    parties_triees = sorted(parties, key=lambda p: p.get("numero", 0) or 0)
    en_cours = {}
    max_streak = {}

    for p in parties_triees:
        pts1 = p.get("pts1", None)
        pts2 = p.get("pts2", None)
        pts1 = int(pts1) if pts1 not in (None, "") else None
        pts2 = int(pts2) if pts2 not in (None, "") else None
        if pts1 is None or pts2 is None:
            continue

        equipe1 = [j for j in [p.get("na", ""), p.get("nb", "")] if j]
        equipe2 = [j for j in [p.get("nc", ""), p.get("nd", "")] if j]

        for joueurs, mes_pts, pts_adv, gagne in (
            (equipe1, pts1, pts2, pts1 == 121),
            (equipe2, pts2, pts1, pts2 == 121),
        ):
            for joueur in joueurs:
                if condition(mes_pts, pts_adv, gagne):
                    en_cours[joueur] = en_cours.get(joueur, 0) + 1
                else:
                    en_cours[joueur] = 0
                if en_cours[joueur] > max_streak.get(joueur, 0):
                    max_streak[joueur] = en_cours[joueur]

    return max_streak


def _trouver_extreme_moyenne(stats_par_joueur, mode="min"):
    """Retourne (valeur, "N parties - Surnom, ...") pour la moyenne la plus
    basse ('min') ou la plus haute ('max') parmi les joueurs ayant joué
    au moins une partie."""
    candidats = {s: v["points_tot"] / v["nbr_parties"]
                 for s, v in stats_par_joueur.items() if v["nbr_parties"] > 0}
    if not candidats:
        return 0, ""
    extreme = round(min(candidats.values()) if mode == "min" else max(candidats.values()), 2)
    gagnants = sorted(s for s, v in candidats.items() if round(v, 2) == extreme)
    texte = ", ".join(f"{stats_par_joueur[s]['nbr_parties']} parties - {s}" for s in gagnants)
    return extreme, texte


def trouver_beau_skunk(parties):
    """Retourne (score, "Perdant1 / Perdant2 par Gagnant1 / Gagnant2") pour le
    skunk (perte à 90 pts ou moins) avec le score perdant le plus bas de la
    soirée. En cas d'égalité, garde la première partie rencontrée (ordre numero)."""
    parties_triees = sorted(parties, key=lambda p: p.get("numero", 0) or 0)
    meilleur = None  # (score, [equipe_perdante], [equipe_gagnante])

    for p in parties_triees:
        pts1 = p.get("pts1", None)
        pts2 = p.get("pts2", None)
        pts1 = int(pts1) if pts1 not in (None, "") else None
        pts2 = int(pts2) if pts2 not in (None, "") else None
        if pts1 is None or pts2 is None:
            continue

        equipe1 = [j for j in [p.get("na", ""), p.get("nb", "")] if j]
        equipe2 = [j for j in [p.get("nc", ""), p.get("nd", "")] if j]

        if pts1 == 121 and pts2 <= 90:
            perdant, gagnant, score = equipe2, equipe1, pts2
        elif pts2 == 121 and pts1 <= 90:
            perdant, gagnant, score = equipe1, equipe2, pts1
        else:
            continue

        if meilleur is None or score < meilleur[0]:
            meilleur = (score, perdant, gagnant)

    if meilleur is None:
        return 0, ""

    score, perdant, gagnant = meilleur
    texte = f"{' / '.join(perdant)} par {' / '.join(gagnant)}"
    return score, texte


# ──────────────────────────────────────────────
# IMPORT SOIRÉE
# ──────────────────────────────────────────────
def importer_soiree(data, conn, lookup):
    c = conn.cursor()

    soiree_num     = int(data.get("soireeNum", 0) or 0)
    soiree_vie_num = int(data.get("soireeVie", 0) or 0)
    saison         = data.get("saison", "")
    date           = data.get("date", "")
    endroit        = data.get("endroit", "")
    prochaine      = data.get("prochaineRencontre", {})
    prochaine_chez = prochaine.get("chez", "")
    prochaine_date = prochaine.get("date", "")
    importe_le     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Supprime la soirée existante si même numéro (ré-import)
    c.execute("SELECT id FROM soirees WHERE soiree_num = ?", (soiree_num,))
    row = c.fetchone()
    if row:
        old_id = row[0]
        c.execute("DELETE FROM parties WHERE soiree_id = ?", (old_id,))
        c.execute("DELETE FROM presence WHERE soiree_id = ?", (old_id,))
        c.execute("DELETE FROM stats_joueurs WHERE soiree_id = ?", (old_id,))
        c.execute("DELETE FROM stats_soiree WHERE soiree_id = ?", (old_id,))
        c.execute("DELETE FROM soirees WHERE id = ?", (old_id,))
        print(f"  ⚠️  Soirée #{soiree_num} déjà présente — remplacée.")

    c.execute("""
        INSERT INTO soirees
            (soiree_num, soiree_vie_num, saison, date, endroit, prochaine_chez, prochaine_date, importe_le)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (soiree_num, soiree_vie_num, saison, date, endroit, prochaine_chez, prochaine_date, importe_le))

    soiree_id = c.lastrowid

    # Parties (joueur_a/b/c/d = surnom, référence vers profiles.surnom)
    parties = data.get("parties", [])
    for p in parties:
        pts1 = p.get("pts1", None)
        pts2 = p.get("pts2", None)
        pts1 = int(pts1) if pts1 not in (None, "") else None
        pts2 = int(pts2) if pts2 not in (None, "") else None
        c.execute("""
            INSERT INTO parties (soiree_id, numero, joueur_a, joueur_b, points_1, points_2, joueur_c, joueur_d)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (soiree_id, p.get("numero"), p.get("na",""), p.get("nb",""),
              pts1, pts2, p.get("nc",""), p.get("nd","")))

    # Présence (surnom + prenom/nom copiés du profil)
    presence = data.get("presence", [])
    for p in presence:
        surnom = p.get("nom", "")
        prenom, nom_famille = lookup.get(surnom, (None, None))
        c.execute("""
            INSERT INTO presence (soiree_id, surnom, prenom, nom, numero)
            VALUES (?, ?, ?, ?, ?)
        """, (soiree_id, surnom, prenom, nom_famille, p.get("numero","")))

    # Stats joueurs de la soirée (calculées à partir des parties)
    stats_par_joueur = calculer_stats_joueurs_soiree(parties)
    for surnom, s in stats_par_joueur.items():
        moyenne = round(s["points_tot"] / s["nbr_parties"], 2) if s["nbr_parties"] else 0
        c.execute("""
            INSERT INTO stats_joueurs
                (soiree_id, surnom, points_tot, nbr_parties, moyenne,
                 parties_g, parties_p, skunks_g, skunks_p, dbl_skunks_g, dbl_skunks_p)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (soiree_id, surnom, s["points_tot"], s["nbr_parties"], moyenne,
              s["parties_g"], s["parties_p"], s["skunks_g"], s["skunks_p"],
              s["dbl_skunks_g"], s["dbl_skunks_p"]))

    # Meneurs de la soirée (stats_soiree)
    skunks_perdus_totaux = {surnom: s["skunks_p"] for surnom, s in stats_par_joueur.items()}
    skunks_perdus_nbr, skunks_perdus_surnoms = _trouver_meneurs(skunks_perdus_totaux)

    skunks_gagnes_totaux = {surnom: s["skunks_g"] for surnom, s in stats_par_joueur.items()}
    skunks_gagnes_nbr, skunks_gagnes_surnoms = _trouver_meneurs(skunks_gagnes_totaux)

    defaites_totales = {surnom: s["parties_p"] for surnom, s in stats_par_joueur.items()}
    defaites_nbr, defaites_surnoms = _trouver_meneurs(defaites_totales)

    victoires_totales = {surnom: s["parties_g"] for surnom, s in stats_par_joueur.items()}
    victoires_nbr, victoires_surnoms = _trouver_meneurs(victoires_totales)

    skunks_perdus_cons = calculer_streak_max(parties, lambda mp, pa, g: (not g) and mp <= 90)
    skunks_perdus_cons_nbr, skunks_perdus_cons_surnoms = _trouver_meneurs(skunks_perdus_cons)

    skunks_gagnes_cons = calculer_streak_max(parties, lambda mp, pa, g: g and pa <= 90)
    skunks_gagnes_cons_nbr, skunks_gagnes_cons_surnoms = _trouver_meneurs(skunks_gagnes_cons)

    defaites_cons = calculer_streak_max(parties, lambda mp, pa, g: not g)
    defaites_cons_nbr, defaites_cons_surnoms = _trouver_meneurs(defaites_cons)

    victoires_cons = calculer_streak_max(parties, lambda mp, pa, g: g)
    victoires_cons_nbr, victoires_cons_surnoms = _trouver_meneurs(victoires_cons)

    basse_moy_nbr, basse_moy_surnom = _trouver_extreme_moyenne(stats_par_joueur, mode="min")
    haute_moy_nbr, haute_moy_surnom = _trouver_extreme_moyenne(stats_par_joueur, mode="max")

    evenements_texte = "; ".join(data.get("evenements", []) or [])

    beau_skunk_soiree, beau_skunk_soiree_par = trouver_beau_skunk(parties)

    c.execute("""
        INSERT INTO stats_soiree
            (soiree_id, date, saison,
             skunks_perdus_nbr, skunks_perdus_surnoms,
             skunks_perdus_cons_nbr, skunks_perdus_cons_surnoms,
             skunks_gagnes_nbr, skunks_gagnes_surnoms,
             skunks_gagnes_cons_nbr, skunks_gagnes_cons_surnoms,
             defaites_nbr, defaites_surnoms,
             defaites_cons_nbr, defaites_cons_surnoms,
             victoires_nbr, victoires_surnoms,
             victoires_cons_nbr, victoires_cons_surnoms,
             basse_moy_nbr, basse_moy_surnom,
             haute_moy_nbr, haute_moy_surnom,
             evenements,
             beau_skunk_soiree, beau_skunk_soiree_par)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (soiree_id, date, saison,
          skunks_perdus_nbr, skunks_perdus_surnoms,
          skunks_perdus_cons_nbr, skunks_perdus_cons_surnoms,
          skunks_gagnes_nbr, skunks_gagnes_surnoms,
          skunks_gagnes_cons_nbr, skunks_gagnes_cons_surnoms,
          defaites_nbr, defaites_surnoms,
          defaites_cons_nbr, defaites_cons_surnoms,
          victoires_nbr, victoires_surnoms,
          victoires_cons_nbr, victoires_cons_surnoms,
          basse_moy_nbr, basse_moy_surnom,
          haute_moy_nbr, haute_moy_surnom,
          evenements_texte,
          beau_skunk_soiree, beau_skunk_soiree_par))

    conn.commit()
    print(f"  ✅ Soirée #{soiree_num} ({date}) importée — {len(parties)} parties, {len(presence)} joueurs présents.")
    return soiree_id, soiree_num, soiree_vie_num, saison, date, endroit, parties, presence


# ──────────────────────────────────────────────
# MISE À JOUR STATS (saison ou à vie)
# ──────────────────────────────────────────────
def maj_stats(conn, table_stats, table_soirees,
              soiree_num, soiree_vie_num, saison, date, endroit, parties, presence,
              champ_soiree_num, lookup, remplir_joueurs=True):
    c = conn.cursor()
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Collecte stats par joueur (clé = surnom)
    stats = {}  # surnom -> {points, parties}

    for p in parties:
        pts1 = p.get("pts1", None)
        pts2 = p.get("pts2", None)
        pts1 = int(pts1) if pts1 not in (None, "") else None
        pts2 = int(pts2) if pts2 not in (None, "") else None

        equipe1 = [j for j in [p.get("na",""), p.get("nb","")] if j]
        equipe2 = [j for j in [p.get("nc",""), p.get("nd","")] if j]

        for joueur in equipe1:
            if joueur not in stats:
                stats[joueur] = {"points": 0, "parties": 0}
            stats[joueur]["parties"] += 1
            if pts1 is not None:
                stats[joueur]["points"] += pts1

        for joueur in equipe2:
            if joueur not in stats:
                stats[joueur] = {"points": 0, "parties": 0}
            stats[joueur]["parties"] += 1
            if pts2 is not None:
                stats[joueur]["points"] += pts2

    # Mise à jour stats joueurs (désactivable — ex: stats_a_vie_joueurs a un
    # schéma incompatible en attendant sa propre logique de remplissage)
    if remplir_joueurs:
        for surnom, s in stats.items():
            prenom, nom_famille = lookup.get(surnom, (None, None))
            c.execute(f"SELECT id, parties_jouees, total_points, soirees FROM {table_stats} WHERE surnom = ?", (surnom,))
            row = c.fetchone()
            if row:
                new_parties = row[1] + s["parties"]
                new_points  = row[2] + s["points"]
                new_soirees = row[3] + 1
                c.execute(f"""
                    UPDATE {table_stats}
                    SET prenom=?, nom=?, parties_jouees=?, total_points=?, soirees=?, derniere_maj=?
                    WHERE surnom=?
                """, (prenom, nom_famille, new_parties, new_points, new_soirees, maintenant, surnom))
            else:
                c.execute(f"""
                    INSERT INTO {table_stats} (surnom, prenom, nom, parties_jouees, total_points, soirees, derniere_maj)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (surnom, prenom, nom_famille, s["parties"], s["points"], maintenant))

    # Enregistrement soirée dans le résumé
    nb_joueurs = len(set(
        [p.get("na","") for p in parties if p.get("na")] +
        [p.get("nb","") for p in parties if p.get("nb")] +
        [p.get("nc","") for p in parties if p.get("nc")] +
        [p.get("nd","") for p in parties if p.get("nd")]
    ))

    champ_val = soiree_vie_num if champ_soiree_num == "soiree_vie_num" else soiree_num

    c.execute(f"SELECT id FROM {table_soirees} WHERE {champ_soiree_num} = ?", (champ_val,))
    if c.fetchone():
        c.execute(f"""
            UPDATE {table_soirees}
            SET saison=?, date=?, endroit=?, nb_parties=?, nb_joueurs=?
            WHERE {champ_soiree_num}=?
        """, (saison, date, endroit, len(parties), nb_joueurs, champ_val))
    else:
        if champ_soiree_num == "soiree_vie_num":
            c.execute(f"""
                INSERT INTO {table_soirees} (soiree_num, soiree_vie_num, saison, date, endroit, nb_parties, nb_joueurs)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (soiree_num, soiree_vie_num, saison, date, endroit, len(parties), nb_joueurs))
        else:
            c.execute(f"""
                INSERT INTO {table_soirees} (soiree_num, saison, date, endroit, nb_parties, nb_joueurs)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (soiree_num, saison, date, endroit, len(parties), nb_joueurs))

    conn.commit()
    print(f"  ✅ Stats mises à jour — {len(stats)} joueurs, {len(parties)} parties.")


# ──────────────────────────────────────────────
# RAPPORT RAPIDE
# ──────────────────────────────────────────────
def afficher_rapport(data, parties, presence):
    print()
    print("─" * 50)
    print(f"  LIGUE DE CRIBLE «DOUBLE-SKUNK»")
    print(f"  Soirée #{data.get('soireeNum')} (à vie #{data.get('soireeVie')})")
    print(f"  Date    : {data.get('date','?')}")
    print(f"  Endroit : {data.get('endroit','?')}")
    print(f"  Parties : {len(parties)}")
    proch = data.get("prochaineRencontre", {})
    if proch.get("chez") or proch.get("date"):
        print(f"  Prochaine rencontre : chez {proch.get('chez','?')} le {proch.get('date','?')}")
    print()
    if presence:
        print(f"  Présence ({len(presence)} joueurs) :")
        for p in sorted(presence, key=lambda x: x.get("nom","")):
            num = f"  #{p.get('numero','')}" if p.get("numero") else ""
            print(f"    • {p.get('nom','')}{num}")
    print("─" * 50)
    print()


# ──────────────────────────────────────────────
# TOTAUX DE LA SOIRÉE (pour stats_saison)
# ──────────────────────────────────────────────
def compter_skunks_soiree(parties):
    """Retourne le nombre total de skunks (perte à 90 pts ou moins) dans la soirée."""
    nb = 0
    for p in parties:
        pts1 = p.get("pts1", None)
        pts2 = p.get("pts2", None)
        pts1 = int(pts1) if pts1 not in (None, "") else None
        pts2 = int(pts2) if pts2 not in (None, "") else None
        if pts1 is None or pts2 is None:
            continue
        if (pts1 == 121 and pts2 <= 90) or (pts2 == 121 and pts1 <= 90):
            nb += 1
    return nb


def trouver_tous_skunks(parties):
    """Retourne une liste de (score, equipe_perdante, equipe_gagnante) pour
    CHAQUE skunk (perte à 90 pts ou moins) de la soirée, dans l'ordre des parties."""
    parties_triees = sorted(parties, key=lambda p: p.get("numero", 0) or 0)
    skunks = []

    for p in parties_triees:
        pts1 = p.get("pts1", None)
        pts2 = p.get("pts2", None)
        pts1 = int(pts1) if pts1 not in (None, "") else None
        pts2 = int(pts2) if pts2 not in (None, "") else None
        if pts1 is None or pts2 is None:
            continue

        equipe1 = [j for j in [p.get("na", ""), p.get("nb", "")] if j]
        equipe2 = [j for j in [p.get("nc", ""), p.get("nd", "")] if j]

        if pts1 == 121 and pts2 <= 90:
            skunks.append((pts2, equipe2, equipe1))
        elif pts2 == 121 and pts1 <= 90:
            skunks.append((pts1, equipe1, equipe2))

    return skunks


def maj_plus_bas_skunks_saison(conn, saison, soiree_num, date, parties):
    """Maintient le top 8 des plus bas skunks de la saison, en fusionnant les
    skunks de la soirée importée avec le classement existant."""
    c = conn.cursor()

    # Retire les anciennes entrées de cette soirée (cas d'un ré-import)
    c.execute("DELETE FROM plus_bas_skunks_saison WHERE saison = ? AND soiree_num = ?",
              (saison, soiree_num))

    c.execute("""
        SELECT nbr, date, soiree_num, perdus_par, gagnes_par
        FROM plus_bas_skunks_saison WHERE saison = ?
    """, (saison,))
    classement = [
        {"nbr": r[0], "date": r[1], "soiree_num": r[2], "perdus_par": r[3], "gagnes_par": r[4]}
        for r in c.fetchall()
    ]

    for score, perdant, gagnant in trouver_tous_skunks(parties):
        classement.append({
            "nbr": score, "date": date, "soiree_num": soiree_num,
            "perdus_par": " / ".join(perdant), "gagnes_par": " / ".join(gagnant),
        })

    classement.sort(key=lambda x: x["nbr"])
    top8 = classement[:8]

    c.execute("DELETE FROM plus_bas_skunks_saison WHERE saison = ?", (saison,))
    for rang, item in enumerate(top8, start=1):
        c.execute("""
            INSERT INTO plus_bas_skunks_saison (saison, soiree_num, rang, nbr, date, perdus_par, gagnes_par)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (saison, item["soiree_num"], rang, item["nbr"], item["date"],
              item["perdus_par"], item["gagnes_par"]))

    conn.commit()
    print(f"  ✅ Top 8 plus bas skunks de la saison mis à jour ({len(top8)} entrée(s))")


def maj_record(anc_nbr, anc_text, anc_date, nouv_nbr, nouv_text, nouv_date, mode):
    """Compare une nouvelle valeur à un record existant. mode='max' (plus grand
    gagne) ou 'min' (plus petit gagne). En cas d'égalité, ajoute la nouvelle
    date (et le nouveau texte, s'il y en a un) à la liste existante (séparée
    par virgule) sans dupliquer."""
    if nouv_nbr is None:
        return anc_nbr, anc_text, anc_date
    if anc_nbr is None:
        return nouv_nbr, nouv_text, nouv_date
    if (mode == "max" and nouv_nbr > anc_nbr) or (mode == "min" and nouv_nbr < anc_nbr):
        return nouv_nbr, nouv_text, nouv_date
    if nouv_nbr == anc_nbr:
        dates = anc_date.split(",") if anc_date else []
        if nouv_date and nouv_date not in dates:
            dates.append(nouv_date)
        nouvelle_date_str = ",".join(dates) if dates else anc_date

        if nouv_text is not None:
            textes = anc_text.split(",") if anc_text else []
            if nouv_text not in textes:
                textes.append(nouv_text)
            nouveau_texte_str = ",".join(textes)
        else:
            nouveau_texte_str = anc_text

        return anc_nbr, nouveau_texte_str, nouvelle_date_str
    return anc_nbr, anc_text, anc_date


def formater_nom_court(surnom, lookup):
    """Formate un surnom en 'Prenom L.' (prénom + initiale du nom de famille)."""
    prenom, nom = lookup.get(surnom, (None, None))
    prenom_affiche = prenom if prenom else surnom
    if nom:
        return f"{prenom_affiche} {nom[0].upper()}."
    return prenom_affiche


def formater_equipe(surnoms, lookup):
    return " / ".join(formater_nom_court(s, lookup) for s in surnoms)


def maj_stats_a_vie_joueurs(conn, date, parties, stats_par_joueur, saison_info_joueurs, lookup):
    """Met à jour les totaux à vie et les records personnels de chaque joueur
    dans stats_a_vie_joueurs, à partir de la soirée importée."""
    c = conn.cursor()
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    skunks_perdus_cons = calculer_streak_max(parties, lambda mp, pa, g: (not g) and mp <= 90)
    skunks_gagnes_cons = calculer_streak_max(parties, lambda mp, pa, g: g and pa <= 90)
    defaites_cons = calculer_streak_max(parties, lambda mp, pa, g: not g)
    victoires_cons = calculer_streak_max(parties, lambda mp, pa, g: g)
    tous_skunks = trouver_tous_skunks(parties)

    for surnom, s in stats_par_joueur.items():
        prenom, nom_famille = lookup.get(surnom, (None, None))
        moyenne_soiree_joueur = round(s["points_tot"] / s["nbr_parties"], 2) if s["nbr_parties"] else None
        moyenne_saison_joueur, parties_saison_joueur = saison_info_joueurs.get(surnom, (None, None))

        texte_moy_soiree = f"{s['nbr_parties']} parties" if s["nbr_parties"] else None
        texte_moy_saison = f"{parties_saison_joueur} parties" if parties_saison_joueur else None

        # Plus beau skunk perdu/gagné de la soirée pour ce joueur (score + équipes du match concerné)
        beau_perdu_score = beau_gagne_score = None
        beau_perdu_perdant = beau_perdu_gagnant = None
        beau_gagne_perdant = beau_gagne_gagnant = None
        for score, perdant, gagnant in tous_skunks:
            if surnom in perdant and (beau_perdu_score is None or score < beau_perdu_score):
                beau_perdu_score = score
                beau_perdu_perdant, beau_perdu_gagnant = perdant, gagnant
            if surnom in gagnant and (beau_gagne_score is None or score < beau_gagne_score):
                beau_gagne_score = score
                beau_gagne_perdant, beau_gagne_gagnant = perdant, gagnant

        texte_beau_perdu = None
        if beau_perdu_score is not None:
            texte_beau_perdu = f"{formater_equipe(beau_perdu_perdant, lookup)} par {formater_equipe(beau_perdu_gagnant, lookup)}"

        texte_beau_gagne = None
        if beau_gagne_score is not None:
            # Même format que "perdu" : équipe perdante d'abord, puis "par", puis l'équipe gagnante (celle du joueur)
            texte_beau_gagne = f"{formater_equipe(beau_gagne_perdant, lookup)} par {formater_equipe(beau_gagne_gagnant, lookup)}"

        c.execute("""
            SELECT points, parties, parties_gagnees, parties_perdues,
                   sks_gagnes, dsks_gagnes, sks_perdus, dsks_perdus,
                   plus_beau_skunk_perdu, plus_beau_skunk_perdu_text, plus_beau_skunk_perdu_date,
                   plus_beau_skunk_gagne, plus_beau_skunk_gagne_text, plus_beau_skunk_gagne_date,
                   plus_de_skunks_perdus, plus_de_skunks_perdus_text, plus_de_skunks_perdus_date,
                   de_skunks_cons_perdus, de_skunks_cons_perdus_text, de_skunks_cons_perdus_date,
                   plus_de_skunks_gagnes, plus_de_skunks_gagnes_text, plus_de_skunks_gagnes_date,
                   de_skunks_cons_gagnes, de_skunks_cons_gagnes_text, de_skunks_cons_gagnes_date,
                   plus_de_defaites, plus_de_defaites_text, plus_de_defaites_date,
                   de_defaites_consec, de_defaites_consec_text, de_defaites_consec_date,
                   plus_de_victoires, plus_de_victoires_text, plus_de_victoires_date,
                   de_victoires_consec, de_victoires_consec_text, de_victoires_consec_date,
                   plus_basse_moy_de_soiree, plus_basse_moy_de_soiree_text, plus_basse_moy_de_soiree_date,
                   haute_moy_de_soiree, haute_moy_de_soiree_text, haute_moy_de_soiree_date,
                   plus_basse_moy_de_saison, plus_basse_moy_de_saison_text, plus_basse_moy_de_saison_date,
                   haute_moy_de_saison, haute_moy_de_saison_text, haute_moy_de_saison_date
            FROM stats_a_vie_joueurs WHERE surnom = ?
        """, (surnom,))
        row = c.fetchone()
        if row is None:
            row = [None] * 50

        (points, parties_j, parties_g, parties_p, sks_g, dsks_g, sks_p, dsks_p,
         bp_nbr, bp_txt, bp_date, bg_nbr, bg_txt, bg_date,
         psp_nbr, psp_txt, psp_date, dscp_nbr, dscp_txt, dscp_date,
         psg_nbr, psg_txt, psg_date, dscg_nbr, dscg_txt, dscg_date,
         pd_nbr, pd_txt, pd_date, ddc_nbr, ddc_txt, ddc_date,
         pv_nbr, pv_txt, pv_date, dvc_nbr, dvc_txt, dvc_date,
         bms_nbr, bms_txt, bms_date, hms_nbr, hms_txt, hms_date,
         bmsais_nbr, bmsais_txt, bmsais_date, hmsais_nbr, hmsais_txt, hmsais_date) = row

        # Totaux (addition) + moyenne (calculée)
        points = (points or 0) + s["points_tot"]
        parties_j = (parties_j or 0) + s["nbr_parties"]
        parties_g = (parties_g or 0) + s["parties_g"]
        parties_p = (parties_p or 0) + s["parties_p"]
        sks_g = (sks_g or 0) + s["skunks_g"]
        dsks_g = (dsks_g or 0) + s["dbl_skunks_g"]
        sks_p = (sks_p or 0) + s["skunks_p"]
        dsks_p = (dsks_p or 0) + s["dbl_skunks_p"]
        moy = round(points / parties_j, 2) if parties_j else None

        # Records personnels (nbr + texte + date, texte seulement pour les
        # champs définis jusqu'ici — les autres restent None pour l'instant)
        bp_nbr, bp_txt, bp_date = maj_record(bp_nbr, bp_txt, bp_date, beau_perdu_score, texte_beau_perdu, date, mode="min")
        bg_nbr, bg_txt, bg_date = maj_record(bg_nbr, bg_txt, bg_date, beau_gagne_score, texte_beau_gagne, date, mode="min")
        psp_nbr, psp_txt, psp_date = maj_record(psp_nbr, psp_txt, psp_date, s["skunks_p"], None, date, mode="max")
        dscp_nbr, dscp_txt, dscp_date = maj_record(dscp_nbr, dscp_txt, dscp_date, skunks_perdus_cons.get(surnom), None, date, mode="max")
        psg_nbr, psg_txt, psg_date = maj_record(psg_nbr, psg_txt, psg_date, s["skunks_g"], None, date, mode="max")
        dscg_nbr, dscg_txt, dscg_date = maj_record(dscg_nbr, dscg_txt, dscg_date, skunks_gagnes_cons.get(surnom), None, date, mode="max")
        pd_nbr, pd_txt, pd_date = maj_record(pd_nbr, pd_txt, pd_date, s["parties_p"], None, date, mode="max")
        ddc_nbr, ddc_txt, ddc_date = maj_record(ddc_nbr, ddc_txt, ddc_date, defaites_cons.get(surnom), None, date, mode="max")
        pv_nbr, pv_txt, pv_date = maj_record(pv_nbr, pv_txt, pv_date, s["parties_g"], None, date, mode="max")
        dvc_nbr, dvc_txt, dvc_date = maj_record(dvc_nbr, dvc_txt, dvc_date, victoires_cons.get(surnom), None, date, mode="max")
        bms_nbr, bms_txt, bms_date = maj_record(bms_nbr, bms_txt, bms_date, moyenne_soiree_joueur, texte_moy_soiree, date, mode="min")
        hms_nbr, hms_txt, hms_date = maj_record(hms_nbr, hms_txt, hms_date, moyenne_soiree_joueur, texte_moy_soiree, date, mode="max")
        bmsais_nbr, bmsais_txt, bmsais_date = maj_record(bmsais_nbr, bmsais_txt, bmsais_date, moyenne_saison_joueur, texte_moy_saison, date, mode="min")
        hmsais_nbr, hmsais_txt, hmsais_date = maj_record(hmsais_nbr, hmsais_txt, hmsais_date, moyenne_saison_joueur, texte_moy_saison, date, mode="max")

        c.execute("""
            INSERT INTO stats_a_vie_joueurs
                (surnom, prenom, nom, points, parties, moy, parties_gagnees, parties_perdues,
                 sks_gagnes, dsks_gagnes, sks_perdus, dsks_perdus,
                 plus_beau_skunk_perdu, plus_beau_skunk_perdu_text, plus_beau_skunk_perdu_date,
                 plus_beau_skunk_gagne, plus_beau_skunk_gagne_text, plus_beau_skunk_gagne_date,
                 plus_de_skunks_perdus, plus_de_skunks_perdus_text, plus_de_skunks_perdus_date,
                 de_skunks_cons_perdus, de_skunks_cons_perdus_text, de_skunks_cons_perdus_date,
                 plus_de_skunks_gagnes, plus_de_skunks_gagnes_text, plus_de_skunks_gagnes_date,
                 de_skunks_cons_gagnes, de_skunks_cons_gagnes_text, de_skunks_cons_gagnes_date,
                 plus_de_defaites, plus_de_defaites_text, plus_de_defaites_date,
                 de_defaites_consec, de_defaites_consec_text, de_defaites_consec_date,
                 plus_de_victoires, plus_de_victoires_text, plus_de_victoires_date,
                 de_victoires_consec, de_victoires_consec_text, de_victoires_consec_date,
                 plus_basse_moy_de_soiree, plus_basse_moy_de_soiree_text, plus_basse_moy_de_soiree_date,
                 haute_moy_de_soiree, haute_moy_de_soiree_text, haute_moy_de_soiree_date,
                 plus_basse_moy_de_saison, plus_basse_moy_de_saison_text, plus_basse_moy_de_saison_date,
                 haute_moy_de_saison, haute_moy_de_saison_text, haute_moy_de_saison_date,
                 derniere_maj)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(surnom) DO UPDATE SET
                prenom=excluded.prenom, nom=excluded.nom,
                points=excluded.points, parties=excluded.parties, moy=excluded.moy,
                parties_gagnees=excluded.parties_gagnees, parties_perdues=excluded.parties_perdues,
                sks_gagnes=excluded.sks_gagnes, dsks_gagnes=excluded.dsks_gagnes,
                sks_perdus=excluded.sks_perdus, dsks_perdus=excluded.dsks_perdus,
                plus_beau_skunk_perdu=excluded.plus_beau_skunk_perdu, plus_beau_skunk_perdu_text=excluded.plus_beau_skunk_perdu_text, plus_beau_skunk_perdu_date=excluded.plus_beau_skunk_perdu_date,
                plus_beau_skunk_gagne=excluded.plus_beau_skunk_gagne, plus_beau_skunk_gagne_text=excluded.plus_beau_skunk_gagne_text, plus_beau_skunk_gagne_date=excluded.plus_beau_skunk_gagne_date,
                plus_de_skunks_perdus=excluded.plus_de_skunks_perdus, plus_de_skunks_perdus_text=excluded.plus_de_skunks_perdus_text, plus_de_skunks_perdus_date=excluded.plus_de_skunks_perdus_date,
                de_skunks_cons_perdus=excluded.de_skunks_cons_perdus, de_skunks_cons_perdus_text=excluded.de_skunks_cons_perdus_text, de_skunks_cons_perdus_date=excluded.de_skunks_cons_perdus_date,
                plus_de_skunks_gagnes=excluded.plus_de_skunks_gagnes, plus_de_skunks_gagnes_text=excluded.plus_de_skunks_gagnes_text, plus_de_skunks_gagnes_date=excluded.plus_de_skunks_gagnes_date,
                de_skunks_cons_gagnes=excluded.de_skunks_cons_gagnes, de_skunks_cons_gagnes_text=excluded.de_skunks_cons_gagnes_text, de_skunks_cons_gagnes_date=excluded.de_skunks_cons_gagnes_date,
                plus_de_defaites=excluded.plus_de_defaites, plus_de_defaites_text=excluded.plus_de_defaites_text, plus_de_defaites_date=excluded.plus_de_defaites_date,
                de_defaites_consec=excluded.de_defaites_consec, de_defaites_consec_text=excluded.de_defaites_consec_text, de_defaites_consec_date=excluded.de_defaites_consec_date,
                plus_de_victoires=excluded.plus_de_victoires, plus_de_victoires_text=excluded.plus_de_victoires_text, plus_de_victoires_date=excluded.plus_de_victoires_date,
                de_victoires_consec=excluded.de_victoires_consec, de_victoires_consec_text=excluded.de_victoires_consec_text, de_victoires_consec_date=excluded.de_victoires_consec_date,
                plus_basse_moy_de_soiree=excluded.plus_basse_moy_de_soiree, plus_basse_moy_de_soiree_text=excluded.plus_basse_moy_de_soiree_text, plus_basse_moy_de_soiree_date=excluded.plus_basse_moy_de_soiree_date,
                haute_moy_de_soiree=excluded.haute_moy_de_soiree, haute_moy_de_soiree_text=excluded.haute_moy_de_soiree_text, haute_moy_de_soiree_date=excluded.haute_moy_de_soiree_date,
                plus_basse_moy_de_saison=excluded.plus_basse_moy_de_saison, plus_basse_moy_de_saison_text=excluded.plus_basse_moy_de_saison_text, plus_basse_moy_de_saison_date=excluded.plus_basse_moy_de_saison_date,
                haute_moy_de_saison=excluded.haute_moy_de_saison, haute_moy_de_saison_text=excluded.haute_moy_de_saison_text, haute_moy_de_saison_date=excluded.haute_moy_de_saison_date,
                derniere_maj=excluded.derniere_maj
        """, (surnom, prenom, nom_famille, points, parties_j, moy, parties_g, parties_p,
              sks_g, dsks_g, sks_p, dsks_p,
              bp_nbr, bp_txt, bp_date, bg_nbr, bg_txt, bg_date,
              psp_nbr, psp_txt, psp_date, dscp_nbr, dscp_txt, dscp_date,
              psg_nbr, psg_txt, psg_date, dscg_nbr, dscg_txt, dscg_date,
              pd_nbr, pd_txt, pd_date, ddc_nbr, ddc_txt, ddc_date,
              pv_nbr, pv_txt, pv_date, dvc_nbr, dvc_txt, dvc_date,
              bms_nbr, bms_txt, bms_date, hms_nbr, hms_txt, hms_date,
              bmsais_nbr, bmsais_txt, bmsais_date, hmsais_nbr, hmsais_txt, hmsais_date,
              maintenant))

    conn.commit()
    print(f"  ✅ Stats à vie mises à jour — {len(stats_par_joueur)} joueur(s)")


def maj_stats_saison(conn, saison, soiree_num, date, nb_skunks, texte_skunks, moyenne, texte_moyenne):
    """Insère une nouvelle ligne dans stats_saison reflétant les records de la
    saison à jour (plus/moins de skunks, basse/haute moyenne d'une soirée),
    en comparant la soirée importée aux records précédents de la même saison."""
    c = conn.cursor()

    c.execute("""
        SELECT plus_de_skunks_nbr, plus_de_skunks_text, plus_de_skunks_date, plus_de_skunks_soiree_num,
               moins_de_skunks_nbr, moins_de_skunks_text, moins_de_skunks_date, moins_de_skunks_soiree_num,
               basse_moy_soiree_nbr, basse_moy_soiree_text, basse_moy_date, basse_moy_soiree_num,
               haute_moy_soiree_nbr, haute_moy_soiree_text, haute_moy_date, haute_moy_soiree_num
        FROM stats_saison WHERE saison = ? ORDER BY id DESC LIMIT 1
    """, (saison,))
    row = c.fetchone()

    if row:
        (p_nbr, p_txt, p_date, p_num,
         m_nbr, m_txt, m_date, m_num,
         b_nbr, b_txt, b_date, b_num,
         h_nbr, h_txt, h_date, h_num) = row
    else:
        p_nbr = m_nbr = b_nbr = h_nbr = None
        p_txt = p_date = p_num = m_txt = m_date = m_num = None
        b_txt = b_date = b_num = h_txt = h_date = h_num = None

    if p_nbr is None or nb_skunks > p_nbr:
        p_nbr, p_txt, p_date, p_num = nb_skunks, texte_skunks, date, soiree_num
    if m_nbr is None or nb_skunks < m_nbr:
        m_nbr, m_txt, m_date, m_num = nb_skunks, texte_skunks, date, soiree_num
    if b_nbr is None or moyenne < b_nbr:
        b_nbr, b_txt, b_date, b_num = moyenne, texte_moyenne, date, soiree_num
    if h_nbr is None or moyenne > h_nbr:
        h_nbr, h_txt, h_date, h_num = moyenne, texte_moyenne, date, soiree_num

    c.execute("""
        INSERT INTO stats_saison
            (saison,
             plus_de_skunks_nbr, plus_de_skunks_text, plus_de_skunks_date, plus_de_skunks_soiree_num,
             moins_de_skunks_nbr, moins_de_skunks_text, moins_de_skunks_date, moins_de_skunks_soiree_num,
             basse_moy_soiree_nbr, basse_moy_soiree_text, basse_moy_date, basse_moy_soiree_num,
             haute_moy_soiree_nbr, haute_moy_soiree_text, haute_moy_date, haute_moy_soiree_num)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (saison,
          p_nbr, p_txt, p_date, p_num,
          m_nbr, m_txt, m_date, m_num,
          b_nbr, b_txt, b_date, b_num,
          h_nbr, h_txt, h_date, h_num))

    conn.commit()
    print(f"  ✅ Records de saison mis à jour — skunks: {p_nbr} max / {m_nbr} min, moyenne: {b_nbr} min / {h_nbr} max")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python double_skunk_import.py <fichier.json>")
        sys.exit(1)

    fichier = sys.argv[1]
    if not os.path.exists(fichier):
        print(f"Erreur : fichier introuvable → {fichier}")
        sys.exit(1)

    # Lecture JSON (UTF-8 avec ou sans BOM)
    with open(fichier, encoding="utf-8-sig") as f:
        data = json.load(f)

    print()
    print(f"📂 Lecture de : {fichier}")

    parties  = data.get("parties", [])
    presence = data.get("presence", [])

    afficher_rapport(data, parties, presence)

    # --- DB LIGUE (profiles + finances) ---
    print(f"👤 Base ligue   → {DB_LIGUE}")
    conn_l = sqlite3.connect(DB_LIGUE)
    init_db_ligue(conn_l)
    conn_l.close()

    # Recherche prenom/nom par surnom (utilisée par toutes les autres DB)
    lookup = charger_lookup_profiles()

    # ── DB SOIRÉE ──
    print(f"📋 Base soirée  → {DB_SOIREE}")
    conn_s = sqlite3.connect(DB_SOIREE)
    init_db_soiree(conn_s)
    soiree_id, soiree_num, soiree_vie_num, saison, date, endroit, parties, presence = \
        importer_soiree(data, conn_s, lookup)
    conn_s.close()

    # ── DB SAISON ──
    print(f"📊 Base saison  → {DB_SAISON}")
    conn_sa = sqlite3.connect(DB_SAISON)
    init_db_saison(conn_sa)
    maj_stats(conn_sa, "stats_joueurs", "soirees_saison",
              soiree_num, soiree_vie_num, saison, date, endroit, parties, presence,
              champ_soiree_num="soiree_num", lookup=lookup)

    # Totaux de la soirée (pour stats_saison)
    stats_par_joueur = calculer_stats_joueurs_soiree(parties)
    nb_joueurs_soiree = len(stats_par_joueur)
    nb_parties_soiree = len(parties)
    nb_skunks_soiree = compter_skunks_soiree(parties)
    total_points_soiree = 0
    nb_scores_soiree = 0
    for p in parties:
        pts1 = p.get("pts1", None)
        pts2 = p.get("pts2", None)
        pts1 = int(pts1) if pts1 not in (None, "") else None
        pts2 = int(pts2) if pts2 not in (None, "") else None
        if pts1 is not None and pts2 is not None:
            total_points_soiree += pts1 + pts2
            nb_scores_soiree += 2
    moyenne_soiree = round(total_points_soiree / nb_scores_soiree, 2) if nb_scores_soiree else 0

    texte_skunks = f"{nb_parties_soiree} parties / {nb_joueurs_soiree} joueurs"
    texte_moyenne = (f"{total_points_soiree:,}".replace(",", " ") +
                      f" points, {nb_parties_soiree} parties, {nb_joueurs_soiree} joueurs")

    maj_stats_saison(conn_sa, saison, soiree_num, date,
                      nb_skunks_soiree, texte_skunks, moyenne_soiree, texte_moyenne)

    maj_plus_bas_skunks_saison(conn_sa, saison, soiree_num, date, parties)

    # Moyenne + nombre de parties de saison à ce jour, par joueur (pour stats_a_vie_joueurs)
    saison_info_joueurs = {}
    for surnom in stats_par_joueur:
        c_sa = conn_sa.cursor()
        c_sa.execute("SELECT total_points, parties_jouees FROM stats_joueurs WHERE surnom = ?", (surnom,))
        r = c_sa.fetchone()
        if r and r[1]:
            saison_info_joueurs[surnom] = (round(r[0] / r[1], 2), r[1])

    conn_sa.close()

    # ── DB À VIE ──
    print(f"🏆 Base à vie   → {DB_A_VIE}")
    conn_av = sqlite3.connect(DB_A_VIE)
    init_db_a_vie(conn_av)
    # Le résumé soirees_a_vie est mis à jour via maj_stats (sans toucher aux
    # colonnes joueurs, gérées séparément par maj_stats_a_vie_joueurs ci-dessous).
    maj_stats(conn_av, "stats_a_vie_joueurs", "soirees_a_vie",
              soiree_num, soiree_vie_num, saison, date, endroit, parties, presence,
              champ_soiree_num="soiree_vie_num", lookup=lookup, remplir_joueurs=False)

    maj_stats_a_vie_joueurs(conn_av, date, parties, stats_par_joueur, saison_info_joueurs, lookup)

    conn_av.close()

    print()
    print("✅ Importation complète !")
    print(f"   {DB_LIGUE}   — profils + finances")
    print(f"   {DB_SOIREE}  — détails de la soirée")
    print(f"   {DB_SAISON}  — cumul saison")
    print(f"   {DB_A_VIE}   — cumul à vie")
    print()

    print("📄 Génération du rapport PDF...")
    rapport_pdf.generer_rapport(date)
    print()


if __name__ == "__main__":
    main()
