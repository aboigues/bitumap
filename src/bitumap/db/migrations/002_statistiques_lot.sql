-- Statistiques du lot (FR-023, T069) : résultat par commune, compté à la clôture.
ALTER TABLE lot
    ADD COLUMN nb_terminees integer NOT NULL DEFAULT 0,
    ADD COLUMN nb_echecs    integer NOT NULL DEFAULT 0,
    ADD COLUMN nb_reportees integer NOT NULL DEFAULT 0;

-- Coûts IA au millionième d'euro : un appel coûte environ 0,0003 € ; avec 4 décimales,
-- chaque réservation et chaque ajustement étaient arrondis et le cumul du jour dérivait
-- du coût réel (trouvé par tests/unit/test_journal.py).
ALTER TABLE cout_ia_jour ALTER COLUMN montant_eur TYPE numeric(12, 6);
ALTER TABLE lot ALTER COLUMN cout_ia_eur TYPE numeric(12, 6);
