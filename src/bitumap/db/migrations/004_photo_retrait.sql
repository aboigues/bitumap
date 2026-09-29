-- Trace du retrait d'une photo (003 US3, US5) : qui, quand, pourquoi ; comme pour un relevé.
ALTER TABLE photo
    ADD COLUMN retire_le     timestamptz,
    ADD COLUMN retire_par    uuid,
    ADD COLUMN motif_retrait text CHECK (length(motif_retrait) <= 200);

ALTER TABLE releve ADD CONSTRAINT releve_motif_retrait_court CHECK (length(motif_retrait) <= 200);
