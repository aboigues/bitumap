-- Schéma initial (data-model.md). Compatible PostgreSQL ≥ 14.

CREATE TABLE compte (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email               text NOT NULL UNIQUE CHECK (email = lower(email)),
    cree_le             timestamptz NOT NULL DEFAULT now(),
    derniere_connexion  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE lien_connexion (
    empreinte_jeton  bytea PRIMARY KEY,               -- SHA-256 du jeton ; jamais le jeton
    compte_id        uuid REFERENCES compte(id) ON DELETE CASCADE,  -- nul avant validation
    email            text NOT NULL CHECK (email = lower(email)),
    emis_le          timestamptz NOT NULL DEFAULT now(),
    expire_le        timestamptz NOT NULL,
    utilise_le       timestamptz
);

CREATE TABLE session (
    empreinte_id  bytea PRIMARY KEY,
    compte_id     uuid NOT NULL REFERENCES compte(id) ON DELETE CASCADE,
    jeton_csrf    text NOT NULL,
    cree_le       timestamptz NOT NULL DEFAULT now(),
    expire_le     timestamptz NOT NULL
);

CREATE TABLE preuve_antibot (
    signature    text PRIMARY KEY,
    utilisee_le  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE compteur_quota (
    cle        text PRIMARY KEY,
    valeur     integer NOT NULL DEFAULT 0,
    expire_le  timestamptz NOT NULL
);

CREATE TABLE lot (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    demarre_le          timestamptz NOT NULL DEFAULT now(),
    termine_le          timestamptz,
    nb_demandes         integer NOT NULL DEFAULT 0 CHECK (nb_demandes BETWEEN 0 AND 10),
    duree_regionale_s   double precision,
    cout_ia_eur         numeric(10, 4) NOT NULL DEFAULT 0
);

CREATE TABLE demande (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    commune_insee      text NOT NULL,
    commune_nom        text NOT NULL,
    empreinte          text NOT NULL,
    etat               text NOT NULL DEFAULT 'en_file'
                       CHECK (etat IN ('en_file', 'en_cours', 'terminee', 'en_echec')),
    etape              text CHECK (etape IN ('acquisition', 'calcul', 'rapport')),
    reportee           boolean NOT NULL DEFAULT false,
    cree_le            timestamptz NOT NULL DEFAULT now(),
    pris_en_charge_le  timestamptz,
    termine_le         timestamptz,
    lot_id             uuid REFERENCES lot(id),
    tentatives         integer NOT NULL DEFAULT 0 CHECK (tentatives <= 2),
    erreur_publique    text
);

-- Une seule demande active par empreinte (FR-009).
CREATE UNIQUE INDEX demande_active_unique ON demande (empreinte)
    WHERE etat IN ('en_file', 'en_cours');
CREATE INDEX demande_file ON demande (cree_le) WHERE etat = 'en_file';

CREATE TABLE demandeur_demande (
    demande_id    uuid NOT NULL REFERENCES demande(id) ON DELETE CASCADE,
    compte_id     uuid NOT NULL REFERENCES compte(id) ON DELETE CASCADE,
    compte_quota  boolean NOT NULL DEFAULT false,
    PRIMARY KEY (demande_id, compte_id)
);

CREATE TABLE cout_ia_jour (
    jour        date PRIMARY KEY,
    montant_eur numeric(10, 4) NOT NULL DEFAULT 0
);

CREATE TABLE source_version (
    source           text NOT NULL,
    portee           text NOT NULL,           -- « regionale » ou code INSEE
    date_extraction  date NOT NULL,
    rafraichie_le    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, portee)
);

CREATE TABLE alerte_envoyee (
    cle         text PRIMARY KEY,
    envoyee_le  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ia_cache_point (
    point_id        text NOT NULL,
    millesimes      text NOT NULL,
    modele          text NOT NULL,
    version_prompt  text NOT NULL,
    reponse         jsonb NOT NULL,
    cree_le         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (point_id, millesimes, modele, version_prompt)
);
