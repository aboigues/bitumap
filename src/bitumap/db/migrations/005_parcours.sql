-- Parcours de surveillance (006, data-model) : table éphémère, expirée à 24 h et purgée au
-- début de chaque lot (SC-006) ; seul le compte qui l'a demandé y accède.
CREATE TABLE parcours (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    compte_id                uuid NOT NULL REFERENCES compte(id) ON DELETE CASCADE,
    commune_insee            text NOT NULL CHECK (commune_insee ~ '^\d{5}$'),
    empreinte                text NOT NULL,
    depart_libelle           text NOT NULL CHECK (length(depart_libelle) <= 300),
    depart_lon               double precision NOT NULL,
    depart_lat               double precision NOT NULL,
    niveaux                  text[] NOT NULL CHECK (
        cardinality(niveaux) >= 1 AND niveaux <@ ARRAY['P1a', 'P1b', 'P1c', 'P2', 'P3']
    ),
    mode                     text NOT NULL CHECK (mode IN ('voiture', 'pied')),
    duree_max_min            integer NOT NULL CHECK (duree_max_min BETWEEN 30 AND 480),
    arret_min                integer NOT NULL CHECK (arret_min BETWEEN 0 AND 30),
    exclusion_releves_jours  integer CHECK (exclusion_releves_jours > 0),
    resultat                 jsonb NOT NULL,
    cree_le                  timestamptz NOT NULL DEFAULT now(),
    expire_le                timestamptz NOT NULL DEFAULT now() + interval '24 hours'
);

CREATE INDEX parcours_expire_le ON parcours (expire_le);
CREATE INDEX parcours_compte ON parcours (compte_id);
