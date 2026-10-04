BEGIN TRANSACTION;
INSERT INTO profiles (anciennete, naissance, prenom, nom, surnom, date_entree, tel_maison, cellulaire, adresse, courriel, actif, derniere_maj) 
VALUES (4, '3 oct', 'Paul', 'Gill', 'Paul', '2022-02-09', '', '', '', '', 1, '2026-09-21  15:00:00');
COMMIT;

