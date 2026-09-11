#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
creer_double_skunk_ligue.py
Ligue de Crible «Double-SKUNK» — Script à usage UNIQUE
--------------------------------------------------------------
Crée double_skunk_ligue.db avec deux tables :
    - profiles   : copie complète (schéma + données) de double_skunk_profile.db
    - finances   : nouvelle table, vide, prête à être remplie

Ce script ne modifie ni ne supprime double_skunk_profile.db.
À exécuter UNE SEULE FOIS. Relancer le script réécrase double_skunk_ligue.db
s'il existe déjà (voir la protection ci-dessous).
"""

import sqlite3
import os

PATH_PROJECT = "/home/charles-ubuntu/Crible/Automation/"
DB_DIR = f"{PATH_PROJECT}DB"

DB_PROFILE = os.path.join(DB_DIR, "double_skunk_profile.db")
DB_LIGUE   = os.path.join(DB_DIR, "double_skunk_ligue.db")


def main():
    if not os.path.exists(DB_PROFILE):
        print(f"Erreur : {DB_PROFILE} introuvable.")
        return

    if os.path.exists(DB_LIGUE):
        reponse = input(f"⚠️  {DB_LIGUE} existe déjà. L'écraser ? (o/N) : ").strip().lower()
        if reponse != "o":
            print("Annulé.")
            return
        os.remove(DB_LIGUE)

    conn = sqlite3.connect(DB_LIGUE)
    c = conn.cursor()

    # ── Table profiles (même schéma que double_skunk_profile.db) ──
    c.execute("""
        CREATE TABLE profiles (
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

    # ── Copie des données depuis double_skunk_profile.db ──
    c.execute("ATTACH DATABASE ? AS ancien", (DB_PROFILE,))
    c.execute("""
        INSERT INTO profiles
            (id, prenom, nom, surnom, anciennete, date_entree, naissance,
             tel_maison, cellulaire, adresse, courriel, notes, actif, derniere_maj)
        SELECT
            id, prenom, nom, surnom, anciennete, date_entree, naissance,
            tel_maison, cellulaire, adresse, courriel, notes, actif, derniere_maj
        FROM ancien.profiles
    """)
    nb_copies = c.rowcount
    conn.commit()
    c.execute("DETACH DATABASE ancien")

    # ── Table finances (nouvelle, vide) ──
    c.execute("""
        CREATE TABLE finances (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            id_soiree           INTEGER,
            saison              TEXT,
            en_caisse_depart    REAL,
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
    conn.close()

    print(f"✅ {DB_LIGUE} créée avec succès.")
    print(f"   • profiles  — {nb_copies} profil(s) copié(s) depuis {DB_PROFILE}")
    print(f"   • finances  — table vide créée, prête à être remplie")


if __name__ == "__main__":
    main()
