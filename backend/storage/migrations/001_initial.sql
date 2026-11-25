CREATE TABLE sb_sessions (
 id uuid PRIMARY KEY, credential_hash text NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), expires_at timestamptz NOT NULL
);
CREATE TABLE sb_controls (id integer PRIMARY KEY CHECK (id=1));
INSERT INTO sb_controls VALUES (1);
CREATE TABLE sb_investigations (
 id uuid PRIMARY KEY, owner_session_id uuid NOT NULL REFERENCES sb_sessions(id),
 operation_key text NOT NULL, request_hash text NOT NULL,
 complaint text NOT NULL, ticket_id text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 current_stage text NOT NULL DEFAULT 'support',
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','awaiting_stage','awaiting_review','completed','failed','environment_blocked')),
 state jsonb NOT NULL DEFAULT '{"stage_outputs":{}}', findings jsonb,
 experiment_count integer NOT NULL DEFAULT 0 CHECK(experiment_count BETWEEN 0 AND 8),
 model_call_count integer NOT NULL DEFAULT 0 CHECK(model_call_count BETWEEN 0 AND 10),
 experiment_limit integer NOT NULL CHECK(experiment_limit BETWEEN 1 AND 8),
 model_call_limit integer NOT NULL CHECK(model_call_limit BETWEEN 1 AND 10),
 event_sequence bigint NOT NULL DEFAULT 0,
 UNIQUE(owner_session_id, operation_key)
);
CREATE INDEX sb_investigation_owner ON sb_investigations(owner_session_id, created_at);
CREATE INDEX sb_investigation_status ON sb_investigations(status);
CREATE TABLE sb_stage_executions (
 investigation_id uuid NOT NULL REFERENCES sb_investigations(id), stage text NOT NULL,
 operation_key text NOT NULL, lease_token uuid NOT NULL, fence bigint NOT NULL,
 expires_at timestamptz NOT NULL, status text NOT NULL CHECK(status IN ('running','completed','failed')),
 output_hash text, PRIMARY KEY(investigation_id,stage)
);
CREATE TABLE sb_tool_executions (
 id uuid PRIMARY KEY, investigation_id uuid NOT NULL REFERENCES sb_investigations(id),
 stage text NOT NULL, fence bigint NOT NULL, operation_key text NOT NULL,
 tool_name text NOT NULL, arguments jsonb NOT NULL, arguments_hash text NOT NULL,
 status text NOT NULL CHECK(status IN ('running','succeeded','failed')),
 result jsonb, evidence_ids uuid[] NOT NULL DEFAULT '{}',
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(), completed_at timestamptz,
 UNIQUE(investigation_id,operation_key), UNIQUE(id,investigation_id)
);
CREATE TABLE sb_evidence (
 id uuid PRIMARY KEY, investigation_id uuid NOT NULL REFERENCES sb_investigations(id),
 category text NOT NULL, source_id text NOT NULL, payload jsonb NOT NULL,
 source_reference text, historical_sha text, observed_at timestamptz NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(), content_hash text NOT NULL,
 provenance jsonb NOT NULL, trust text NOT NULL CHECK(trust IN ('untrusted_data','host_assertion')),
 execution_id uuid, FOREIGN KEY(execution_id,investigation_id) REFERENCES sb_tool_executions(id,investigation_id)
);
CREATE INDEX sb_evidence_investigation ON sb_evidence(investigation_id);
CREATE TABLE sb_events (
 id uuid PRIMARY KEY, investigation_id uuid NOT NULL REFERENCES sb_investigations(id),
 sequence bigint NOT NULL, actor text NOT NULL, stage text, event_type text NOT NULL,
 tool_name text, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 evidence_ids uuid[] NOT NULL DEFAULT '{}', UNIQUE(investigation_id,sequence)
);
CREATE TABLE sb_usage_reservations (
 id uuid PRIMARY KEY, investigation_id uuid NOT NULL REFERENCES sb_investigations(id),
 stage text NOT NULL, kind text NOT NULL CHECK(kind IN ('experiment','model')),
 ordinal integer NOT NULL CHECK(ordinal>0), operation_key text NOT NULL,
 execution_id uuid, provider text, model text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), completed_at timestamptz,
 input_tokens bigint CHECK(input_tokens>=0), output_tokens bigint CHECK(output_tokens>=0),
 outcome text NOT NULL DEFAULT 'reserved' CHECK(outcome IN ('reserved','succeeded','failed','unknown')),
 UNIQUE(investigation_id,kind,ordinal), UNIQUE(investigation_id,kind,operation_key),
 FOREIGN KEY(execution_id,investigation_id) REFERENCES sb_tool_executions(id,investigation_id)
);
CREATE TABLE sb_review_drafts (
 investigation_id uuid PRIMARY KEY REFERENCES sb_investigations(id),
 draft jsonb NOT NULL, assertion_id uuid NOT NULL REFERENCES sb_evidence(id),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE sb_escalations (
 id uuid PRIMARY KEY, investigation_id uuid NOT NULL UNIQUE REFERENCES sb_review_drafts(investigation_id),
 draft jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE sb_reviews (
 investigation_id uuid PRIMARY KEY REFERENCES sb_review_drafts(investigation_id),
 decision text NOT NULL CHECK(decision IN ('approved','rejected')),
 reviewer_note text NOT NULL, decided_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 escalation_id uuid UNIQUE REFERENCES sb_escalations(id),
 CHECK((decision='approved')=(escalation_id IS NOT NULL))
);
CREATE FUNCTION sb_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'append-only investigation record'; END;
$$;
CREATE TRIGGER sb_evidence_immutable BEFORE UPDATE OR DELETE ON sb_evidence FOR EACH ROW EXECUTE FUNCTION sb_immutable();
CREATE TRIGGER sb_event_immutable BEFORE UPDATE OR DELETE ON sb_events FOR EACH ROW EXECUTE FUNCTION sb_immutable();
CREATE TRIGGER sb_draft_immutable BEFORE UPDATE OR DELETE ON sb_review_drafts FOR EACH ROW EXECUTE FUNCTION sb_immutable();
CREATE TRIGGER sb_review_immutable BEFORE UPDATE OR DELETE ON sb_reviews FOR EACH ROW EXECUTE FUNCTION sb_immutable();
CREATE TRIGGER sb_escalation_immutable BEFORE UPDATE OR DELETE ON sb_escalations FOR EACH ROW EXECUTE FUNCTION sb_immutable();
