#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vider_finances.py
Ligue de Crible «Double-SKUNK» — Vide la table finances
--------------------------------------------------------------
Efface toutes les données de la table `finances` (double_skunk_ligue.db)
sans toucher au reste de la DB (profiles, schéma). Demande confirmation.
"""

import sqlite3
import os

PATH_PROJECT = "/home/charles-ubuntu/Crible/Automation/"
DB_LIGUE = os.path.join(PATH_PROJECT, "DB", "double_skunk_ligue.db")


def main():
    if not os.path.exists(DB_LIGUE):
        print(f"Erreur : {DB_LIGUE} introuvable.")
        return

    conn = sqlite3.connect(DB_LIGUE)
    c = conn.cursor()

    nb = c.execute("SELECT COUNT(*) FROM finances").fetchone()[0]
    if nb == 0:
        print("La table 'finances' est déjà vide.")
        conn.close()
        return

    reponse = input(f"⚠️  {nb} ligne(s) dans 'finances' seront supprimées. Confirmer ? (o/N) : ").strip().lower()
    if reponse != "o":
        print("Annulé.")
        conn.close()
        return

    c.execute("DELETE FROM finances")
    c.execute("DELETE FROM sqlite_sequence WHERE name='finances'")  # remet le compteur AUTOINCREMENT à 0
    conn.commit()
    conn.close()
    print(f"✅ {nb} ligne(s) supprimée(s) — table 'finances' vidée.")


if __name__ == "__main__":
    main()
