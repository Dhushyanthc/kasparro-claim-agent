CREATE TABLE IF NOT EXISTS runs (
  run_id uuid PRIMARY KEY,
  split text NOT NULL CHECK (split IN ('development','check')),
  agent_version text NOT NULL CHECK (agent_version IN ('v1','v2')),
  status text NOT NULL CHECK (status IN ('running','completed','failed')),
  config jsonb NOT NULL,
  counts jsonb,
  metrics jsonb,
  error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE TABLE IF NOT EXISTS answer_results (
  run_id uuid NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  answer_id text NOT NULL,
  position integer NOT NULL,
  status text NOT NULL CHECK (status IN ('ok','error')),
  error_type text,
  error_message text,
  claim_count integer NOT NULL DEFAULT 0,
  latency_ms integer,
  trace_ref text,
  PRIMARY KEY (run_id, answer_id),
  CHECK ((status = 'ok') = (error_type IS NULL)),
  CHECK (status = 'ok' OR claim_count = 0)
);
CREATE TABLE IF NOT EXISTS claim_results (
  run_id uuid NOT NULL,
  answer_id text NOT NULL,
  claim_id text NOT NULL,
  start_char integer NOT NULL CHECK (start_char >= 0),
  end_char integer NOT NULL,
  quote text NOT NULL,
  label text NOT NULL CHECK (label IN ('supported','contradicted','unknown')),
  fact_ids text[] NOT NULL,
  reason text NOT NULL,
  parts jsonb NOT NULL,
  match jsonb,
  FOREIGN KEY (run_id, answer_id) REFERENCES answer_results(run_id, answer_id) ON DELETE CASCADE,
  UNIQUE (run_id, answer_id, start_char, end_char),
  UNIQUE (run_id, claim_id),
  CHECK (end_char > start_char)
);
