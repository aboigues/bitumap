-- Progression de la génération (009, data-model) : pourcentage (jamais 100 : la fin est
-- l'état « terminee ») et fin estimée pendant les analyses par l'IA ; phases écrites par le
-- job. « acquisition » et « calcul » ne sont plus écrites mais restent admises pour les
-- lignes existantes.
ALTER TABLE demande
    ADD COLUMN avancement  smallint CHECK (avancement IS NULL OR avancement BETWEEN 0 AND 99),
    ADD COLUMN fin_estimee timestamptz;

ALTER TABLE demande DROP CONSTRAINT demande_etape_check;
ALTER TABLE demande ADD CONSTRAINT demande_etape_check
    CHECK (etape IN ('acquisition', 'calcul', 'sources', 'points', 'ia', 'rapport'));
