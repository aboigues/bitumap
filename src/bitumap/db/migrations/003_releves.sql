-- Relevés terrain (specs/003-terrain-releves/data-model.md). Rien n'est modifié en place pour
-- le contenu d'un relevé : toute correction ajoute une version (FR-011).

CREATE TABLE releve (
    id                 uuid PRIMARY KEY,                -- généré sur le téléphone (idempotence)
    commune_insee      text NOT NULL,
    point_id           text NOT NULL,                   -- identifiant stable du point (002 FR-016)
    point_nom          text NOT NULL,
    point_designation  text NOT NULL,
    niveau_estime      text NOT NULL,                   -- groupe P1a … P3 à la saisie
    compte_id          uuid REFERENCES compte(id) ON DELETE SET NULL,  -- nul : auteur supprimé
    cree_le            timestamptz NOT NULL,            -- saisie sur le téléphone
    recu_le            timestamptz NOT NULL DEFAULT now(),
    lon                double precision,
    lat                double precision,
    distance_point_m   double precision,
    retire_le          timestamptz,
    retire_par         uuid,
    motif_retrait      text,
    CHECK ((lon IS NULL) = (lat IS NULL))
);

CREATE INDEX releve_point ON releve (commune_insee, point_id, cree_le DESC);

CREATE TABLE releve_version (
    releve_id              uuid NOT NULL REFERENCES releve(id) ON DELETE CASCADE,
    version                integer NOT NULL CHECK (version >= 1),
    cree_le                timestamptz NOT NULL DEFAULT now(),
    niveau                 text NOT NULL CHECK (niveau IN ('absent', 'leger', 'marque', 'grave')),
    profondeur_mm          integer CHECK (profondeur_mm BETWEEN 0 AND 200),
    instrument             text CHECK (length(instrument) <= 100),
    observation            text CHECK (length(observation) <= 1000),
    annee_refection        integer CHECK (annee_refection >= 1950),  -- borne haute : applicative
    source_refection       text CHECK (source_refection IN
                               ('constatee', 'services_techniques', 'estimee_agent')),
    incoherence_confirmee  boolean NOT NULL DEFAULT false,
    PRIMARY KEY (releve_id, version),
    CHECK (profondeur_mm IS NULL OR instrument IS NOT NULL),
    CHECK (annee_refection IS NULL OR source_refection IS NOT NULL)
);

CREATE TABLE photo (
    id          uuid PRIMARY KEY,                       -- généré sur le téléphone
    releve_id   uuid NOT NULL REFERENCES releve(id) ON DELETE CASCADE,
    cle_objet   text NOT NULL,
    etat        text NOT NULL DEFAULT 'quarantaine' CHECK (etat IN
                    ('quarantaine', 'visible', 'retiree_auteur', 'retiree_mainteneur')),
    octets      integer NOT NULL DEFAULT 0,
    largeur     integer,
    hauteur     integer,
    lon         double precision,
    lat         double precision,
    prise_le    timestamptz,
    cree_le     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX photo_releve ON photo (releve_id);
