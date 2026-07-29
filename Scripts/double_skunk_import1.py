#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
double_skunk_import.py
Ligue de Crible «Double-SKUNK» — Importation JSON vers SQLite
--------------------------------------------------------------
Usage:
    python double_skunk_import.py <fichier.json>

3 bases de données SQLite sont créées/mises à jour :
    double_skunk_soiree.db  — données de la soirée importée
    double_skunk_saison.db  — cumul de la saison en cours
    double_skunk_a_vie.db    — cumul à vie (toutes saisons)
    double_skunk_profile.db — Profile joueur 
"""

import sys
import json
import sqlite3
import os
from datetime import datetime

# ──────────────────────────────────────────────
# FICHIERS DE BASE DE DONNÉES
# ──────────────────────────────────────────────
DB_DIR = "/home/charles-ubuntu/Crible/Automation/DB"
os.makedirs(DB_DIR, exist_ok=True)

DB_SOIREE  = os.path.join(DB_DIR, "double_skunk_soiree.db")
DB_SAISON  = os.path.join(DB_DIR, "double_skunk_saison.db")
DB_A_VIE   = os.path.join(DB_DIR, "double_skunk_a_vie.db")
DB_PROFILE = os.path.join(DB_DIR, "double_skunk_profile.db")


# ──────────────────────────────────────────────
# CRÉATION DES TABLES
# ──────────────────────────────────────────────
def init_db_soiree(conn):
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS soirees (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_num      INTEGER,
            soiree_vie_num  INTEGER,
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS presence (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_id   INTEGER,
            nom         TEXT,
            numero      TEXT,
            FOREIGN KEY (soiree_id) REFERENCES soirees(id)
        )
    """)

    conn.commit()


def init_db_saison(conn):
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS stats_joueurs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nom             TEXT UNIQUE,
            parties_jouees  INTEGER DEFAULT 0,
            total_points    INTEGER DEFAULT 0,
            soirees         INTEGER DEfault 0,
            points_2        INTEGER,
            joueur_c        TEXT,
            meilleur_score  INTEGER DEFAULT 0,
            derniere_maj    TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS soirees_saison (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_num      INTEGER UNIQUE,
            date            TEXT,
            endroit         TEXT,
            nb_parties      INTEGER,
            nb_joueurs      INTEGER
        )
    """)

    conn.commit()


def init_db_a_vie(conn):
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS stats_a_vie (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nom             TEXT UNIQUE,
            parties_jouees  INTEGER DEFAULT 0,
            total_points    INTEGER DEFAULT 0,
            soirees         INTEGER DEFAULT 0,
            meilleur_score  INTEGER DEFAULT 0,
            derniere_maj    TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS soirees_a_vie (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            soiree_num      INTEGER,
            soiree_vie_num  INTEGER UNIQUE,
            date            TEXT,
            endroit         TEXT,
            nb_parties      INTEGER,
            nb_joueurs      INTEGER
        )
    """)

    conn.commit()


# ──────────────────────────────────────────────
# IMPORT SOIRÉE
# ──────────────────────────────────────────────
def importer_soiree(data, conn):
    c = conn.cursor()

    soiree_num     = int(data.get("soireeNum", 0) or 0)
    soiree_vie_num = int(data.get("soireeVie", 0) or 0)
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
        c.execute("DELETE FROM soirees WHERE id = ?", (old_id,))
        print(f"  ⚠️  Soirée #{soiree_num} déjà présente — remplacée.")

    c.execute("""
        INSERT INTO soirees
            (soiree_num, soiree_vie_num, date, endroit, prochaine_chez, prochaine_date, importe_le)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (soiree_num, soiree_vie_num, date, endroit, prochaine_chez, prochaine_date, importe_le))

    soiree_id = c.lastrowid

    # Parties
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

    # Présence
    presence = data.get("presence", [])
    for p in presence:
        c.execute("""
            INSERT INTO presence (soiree_id, nom, numero)
            VALUES (?, ?, ?)
        """, (soiree_id, p.get("nom",""), p.get("numero","")))

    conn.commit()
    print(f"  ✅ Soirée #{soiree_num} ({date}) importée — {len(parties)} parties, {len(presence)} joueurs présents.")
    return soiree_id, soiree_num, soiree_vie_num, date, endroit, parties, presence


# ──────────────────────────────────────────────
# MISE À JOUR STATS (saison ou à vie)
# ──────────────────────────────────────────────
def maj_stats(conn, table_stats, table_soirees,
              soiree_num, soiree_vie_num, date, endroit, parties, presence,
              champ_soiree_num):
    c = conn.cursor()
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Collecte stats par joueur
    stats = {}  # nom -> {points, parties, meilleur}

    for p in parties:
        pts1 = p.get("pts1", None)
        pts2 = p.get("pts2", None)
        pts1 = int(pts1) if pts1 not in (None, "") else None
        pts2 = int(pts2) if pts2 not in (None, "") else None

        equipe1 = [j for j in [p.get("na",""), p.get("nb","")] if j]
        equipe2 = [j for j in [p.get("nc",""), p.get("nd","")] if j]

        for joueur in equipe1:
            if joueur not in stats:
                stats[joueur] = {"points": 0, "parties": 0, "meilleur": 0}
            stats[joueur]["parties"] += 1
            if pts1 is not None:
                stats[joueur]["points"] += pts1
                if pts1 > stats[joueur]["meilleur"]:
                    stats[joueur]["meilleur"] = pts1

        for joueur in equipe2:
            if joueur not in stats:
                stats[joueur] = {"points": 0, "parties": 0, "meilleur": 0}
            stats[joueur]["parties"] += 1
            if pts2 is not None:
                stats[joueur]["points"] += pts2
                if pts2 > stats[joueur]["meilleur"]:
                    stats[joueur]["meilleur"] = pts2

    # Mise à jour stats joueurs
    for nom, s in stats.items():
        c.execute(f"SELECT id, parties_jouees, total_points, soirees, meilleur_score FROM {table_stats} WHERE nom = ?", (nom,))
        row = c.fetchone()
        if row:
            new_parties = row[1] + s["parties"]
            new_points  = row[2] + s["points"]
            new_soirees = row[3] + 1
            new_meilleur = max(row[4], s["meilleur"])
            c.execute(f"""
                UPDATE {table_stats}
                SET parties_jouees=?, total_points=?, soirees=?, meilleur_score=?, derniere_maj=?
                WHERE nom=?
            """, (new_parties, new_points, new_soirees, new_meilleur, maintenant, nom))
        else:
            c.execute(f"""
                INSERT INTO {table_stats} (nom, parties_jouees, total_points, soirees, meilleur_score, derniere_maj)
                VALUES (?, ?, ?, 1, ?, ?)
            """, (nom, s["parties"], s["points"], s["meilleur"], maintenant))

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
            SET date=?, endroit=?, nb_parties=?, nb_joueurs=?
            WHERE {champ_soiree_num}=?
        """, (date, endroit, len(parties), nb_joueurs, champ_val))
    else:
        if champ_soiree_num == "soiree_vie_num":
            c.execute(f"""
                INSERT INTO {table_soirees} (soiree_num, soiree_vie_num, date, endroit, nb_parties, nb_joueurs)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (soiree_num, soiree_vie_num, date, endroit, len(parties), nb_joueurs))
        else:
            c.execute(f"""
                INSERT INTO {table_soirees} (soiree_num, date, endroit, nb_parties, nb_joueurs)
                VALUES (?, ?, ?, ?, ?)
            """, (soiree_num, date, endroit, len(parties), nb_joueurs))

    conn.commit()
    print(f" avie ✅ Stats mises à jour — {len(stats)} joueurs, {len(parties)} parties.")


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

    # ── DB SOIRÉE ──
    print(f"📋 Base soirée  → {DB_SOIREE}")
    conn_s = sqlite3.connect(DB_SOIREE)
    init_db_soiree(conn_s)
    soiree_id, soiree_num, soiree_vie_num, date, endroit, parties, presence = \
        importer_soiree(data, conn_s)
    conn_s.close()

    # ── DB SAISON ──
    print(f"📊a vie Base saison  → {DB_SAISON}")
    conn_sa = sqlite3.connect(DB_SAISON)
    init_db_saison(conn_sa)
    maj_stats(conn_sa, "stats_joueurs", "soirees_saison",
              soiree_num, soiree_vie_num, date, endroit, parties, presence,
              champ_soiree_num="soiree_num")
    conn_sa.close()

    # ── DB À VIE ──
    print(f"🏆 Base à vie   → {DB_A_VIE}")
    conn_av = sqlite3.connect(DB_A_VIE)
    init_db_a_vie(conn_av)
    maj_stats(conn_av, "stats_a_vie", "soirees_a_vie",
              soiree_num, soiree_vie_num, date, endroit, parties, presence,
              champ_soiree_num="soiree_vie_num")
    conn_av.close()

    print()
    print("✅ Importation complète !")
    print(f"   {DB_SOIREE}  — détails de la soirée")
    print(f"   {DB_SAISON}  — cumul saison")
    print(f"   {DB_A_VIE}    — cumul à vie")
    print()


if __name__ == "__main__":
    main()
