#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generer_rapport.py
Ligue de Crible «Double-SKUNK» — Génération d'un rapport PDF à la demande
--------------------------------------------------------------
Demande une date de soirée et génère le rapport PDF (soirée + saison)
correspondant, à partir des bases de données déjà importées.

Usage :
    python generer_rapport.py                # demande la date interactivement
    python generer_rapport.py 2026-08-28      # date fournie en argument
"""

import sys
from rapport_pdf import generer_rapport


def main():
    if len(sys.argv) >= 2:
        date_soiree = sys.argv[1].strip()
    else:
        date_soiree = input("Date de la soirée (AAAA-MM-JJ) : ").strip()

    if not date_soiree:
        print("Aucune date fournie.")
        return

    chemin = generer_rapport(date_soiree)
    if chemin:
        print(f"\n✅ Rapport généré : {chemin}")
    else:
        print(f"\n❌ Aucune soirée trouvée pour la date « {date_soiree} ».")


if __name__ == "__main__":
    main()
