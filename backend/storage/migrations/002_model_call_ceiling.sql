-- Preserve migration 001 and safely upgrade existing investigation tables.
ALTER TABLE sb_investigations
    DROP CONSTRAINT sb_investigations_model_call_count_check,
    ADD CONSTRAINT sb_investigations_model_call_count_check
        CHECK (model_call_count BETWEEN 0 AND 20),
    DROP CONSTRAINT sb_investigations_model_call_limit_check,
    ADD CONSTRAINT sb_investigations_model_call_limit_check
        CHECK (model_call_limit BETWEEN 1 AND 20);
