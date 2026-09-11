#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corriger_finances.py
Ligue de Crible «Double-SKUNK» — Correction ponctuelle
--------------------------------------------------------------
Corrige la table `finances` de double_skunk_ligue.db si sa colonne
'en_caisse_départ' (avec accent) est manquante ou mal nommée, SANS perdre
les données déjà présentes (renomme la colonne, ou ajoute la colonne).

À exécuter UNE SEULE FOIS.
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

    existe = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='finances'"
    ).fetchone()
    if not existe:
        print("La table 'finances' n'existe pas encore — rien à corriger, "
              "elle sera créée normalement au prochain import.")
        conn.close()
        return

    c.execute("PRAGMA table_info(finances)")
    colonnes = [row[1] for row in c.fetchall()]
    print(f"Colonnes actuelles de 'finances' : {colonnes}")

    if "en_caisse_départ" in colonnes:
        print("✅ La colonne 'en_caisse_départ' existe déjà — rien à faire.")
        conn.close()
        return

    # Cherche une variante probable (sans accent, ou autre variante d'encodage)
    candidates = [c for c in colonnes if c.lower().replace("é", "e").replace("è", "e") == "en_caisse_depart"]

    if candidates:
        ancien_nom = candidates[0]
        print(f"Renommage de '{ancien_nom}' → 'en_caisse_départ'...")
        c.execute(f'ALTER TABLE finances RENAME COLUMN "{ancien_nom}" TO en_caisse_départ')
        conn.commit()
        print("✅ Colonne renommée avec succès — les données existantes sont conservées.")
    else:
        print("Aucune colonne existante trouvée — ajout de 'en_caisse_départ' (vide pour les lignes existantes).")
        c.execute("ALTER TABLE finances ADD COLUMN en_caisse_départ REAL")
        conn.commit()
        print("✅ Colonne ajoutée.")

    conn.close()


if __name__ == "__main__":
    main()
