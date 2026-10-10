-- Forward-only integration migration; 001 and its ledger remain unchanged.
ALTER TABLE datasets ADD COLUMN metadata jsonb NOT NULL DEFAULT '{}';
ALTER TABLE dataset_versions ADD COLUMN metadata jsonb NOT NULL DEFAULT '{}';

CREATE TABLE feedback_records (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 version_id bigint NOT NULL REFERENCES dataset_versions,
 external_id text NOT NULL, model_code text NOT NULL REFERENCES models,
 market_code text REFERENCES markets, raw_market text, statement text NOT NULL,
 publication_date date, source_platform text, feedback_type text,
 UNIQUE(version_id,external_id), UNIQUE(id,version_id)
);
CREATE TABLE feedback_tags (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 feedback_id bigint NOT NULL, version_id bigint NOT NULL,
 source_record_id bigint NOT NULL UNIQUE,
 original_tags jsonb NOT NULL,
 FOREIGN KEY(feedback_id,version_id) REFERENCES feedback_records(id,version_id),
 FOREIGN KEY(source_record_id,version_id) REFERENCES source_records(id,version_id)
);
CREATE TABLE evidence_items (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 version_id bigint NOT NULL, source_record_id bigint NOT NULL,
 feedback_id bigint, model_code text NOT NULL REFERENCES models,
 market_code text REFERENCES markets, variant_id bigint,
 category_id text REFERENCES categories, category_mapping_version text,
 mapping_status text NOT NULL DEFAULT 'needs_review' CHECK(mapping_status IN ('needs_review','reviewed','unmapped')),
 evidence_kind text NOT NULL CHECK(evidence_kind IN ('customer_statement','published_specification','derived_assessment')),
 source_platform text, title text NOT NULL, statement text NOT NULL,
 source_url text, publication_date date, captured_at timestamptz NOT NULL DEFAULT now(),
 data_origin text NOT NULL CHECK(data_origin IN ('observed','synthetic','unknown')),
 scope_layer text NOT NULL DEFAULT 'fixed' CHECK(scope_layer IN ('fixed','variable','hypothetical')),
 review_status text NOT NULL DEFAULT 'unreviewed' CHECK(review_status IN ('unreviewed','reviewed','rejected')),
 safety_review boolean NOT NULL DEFAULT false,
 context jsonb NOT NULL DEFAULT '{}',
 UNIQUE(source_record_id,evidence_kind),
 FOREIGN KEY(source_record_id,version_id) REFERENCES source_records(id,version_id),
 FOREIGN KEY(version_id,data_origin) REFERENCES dataset_versions(id,data_origin),
 FOREIGN KEY(feedback_id,version_id) REFERENCES feedback_records(id,version_id),
 FOREIGN KEY(variant_id,model_code) REFERENCES variants(id,model_code)
);
CREATE INDEX evidence_cohort ON evidence_items(model_code,market_code,version_id,evidence_kind);

CREATE TABLE processing_runs (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 version_id bigint REFERENCES dataset_versions,
 algorithm_version text NOT NULL, model_name text, prompt_version text,
 taxonomy_version text NOT NULL, input_assumptions jsonb NOT NULL,
 status text NOT NULL CHECK(status IN ('succeeded','quarantined','disabled')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE problem_proposals (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 model_code text NOT NULL REFERENCES models, market_code text REFERENCES markets,
 category_id text NOT NULL REFERENCES categories,
 scope_layer text NOT NULL CHECK(scope_layer IN ('fixed','variable','hypothetical')),
 title text NOT NULL, summary text NOT NULL, created_by text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), method text NOT NULL DEFAULT 'manual',
 priority_status text NOT NULL DEFAULT 'unscored' CHECK(priority_status='unscored'),
 review_status text NOT NULL DEFAULT 'unreviewed'
);
CREATE TABLE problem_evidence (
 problem_id bigint REFERENCES problem_proposals, evidence_id bigint REFERENCES evidence_items,
 PRIMARY KEY(problem_id,evidence_id)
);
CREATE TABLE requirements (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 problem_id bigint NOT NULL UNIQUE REFERENCES problem_proposals,
 model_code text NOT NULL REFERENCES models, market_code text REFERENCES markets,
 category_id text NOT NULL REFERENCES categories,
 scope_layer text NOT NULL CHECK(scope_layer IN ('fixed','variable','hypothetical')),
 current_revision integer NOT NULL DEFAULT 1 CHECK(current_revision>0),
 status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','rejected','postponed')),
 review_date date, postponement_unscheduled boolean NOT NULL DEFAULT false,
 verification_status text NOT NULL DEFAULT 'unverified' CHECK(verification_status IN ('unverified','verified')),
 created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE requirement_versions (
 requirement_id bigint REFERENCES requirements, revision integer CHECK(revision>0),
 title text NOT NULL, statement text NOT NULL, baseline_value text, target_value numeric,
 unit text, conditions text, acceptance_test text, owner text,
 specification_status text NOT NULL CHECK(specification_status IN ('needs_specification','specified')),
 created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(requirement_id,revision)
);
ALTER TABLE requirements ADD CONSTRAINT requirement_current_version
 FOREIGN KEY(id,current_revision) REFERENCES requirement_versions(requirement_id,revision) DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE requirement_evidence (
 requirement_id bigint, revision integer, evidence_id bigint NOT NULL REFERENCES evidence_items,
 PRIMARY KEY(requirement_id,revision,evidence_id),
 FOREIGN KEY(requirement_id,revision) REFERENCES requirement_versions(requirement_id,revision)
);
CREATE TABLE pm_decisions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 requirement_id bigint NOT NULL REFERENCES requirements,
 resulting_revision integer NOT NULL,
 action text NOT NULL CHECK(action IN ('approve','edit','reject','postpone')),
 rationale text NOT NULL CHECK(length(trim(rationale))>0),
 actor text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(requirement_id,resulting_revision) REFERENCES requirement_versions(requirement_id,revision)
);
CREATE TABLE audit_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 requirement_id bigint NOT NULL REFERENCES requirements,
 revision integer NOT NULL, action text NOT NULL, actor text NOT NULL,
 rationale text NOT NULL, before_state jsonb, after_state jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(requirement_id,revision) REFERENCES requirement_versions(requirement_id,revision)
);
CREATE FUNCTION reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Audit events are append-only for application access'; END $$;
CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_events
 FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation();
REVOKE ALL ON audit_events FROM PUBLIC;
-- Owners can override protections; application roles receive SELECT/INSERT only.
