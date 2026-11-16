-- OWNER: R1 (provisional, ADR-003). DDL [Propuesto] de README §13.2. R1 asume el contenido por PR.
CREATE TABLE prov.citation (
  citation_id serial PRIMARY KEY, bibkey text UNIQUE NOT NULL, full_text text NOT NULL, doi text, url text);

CREATE TABLE prov.data_source (
  source_id smallint PRIMARY KEY, code text UNIQUE NOT NULL,
  product_name text NOT NULL, institution text NOT NULL,
  is_nasa boolean NOT NULL, version text, spatial_res_m integer, temporal_res interval,
  license text, redistributable boolean NOT NULL DEFAULT false, access_url text,
  citation_id integer REFERENCES prov.citation);

CREATE TABLE prov.ingestion_run (
  ingestion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id smallint NOT NULL REFERENCES prov.data_source,
  query_params jsonb NOT NULL, queried_at timestamptz NOT NULL DEFAULT now(),
  period_start date, period_end date,
  raw_uri text NOT NULL, raw_sha256 char(64) NOT NULL, n_records bigint,
  status text NOT NULL CHECK (status IN ('ok','partial','failed')), report jsonb);

CREATE TABLE prov.indicator_provenance (
  ip_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid,                                    -- FK a engine.analysis_run se agrega en la revisión engine
  indicator_code text NOT NULL, unit text NOT NULL,
  provenance provenance_t NOT NULL, evidence_level evidence_t,
  source_ids smallint[] NOT NULL, ingestion_ids uuid[], dataset_version text,
  period_start date, period_end date, spatial_res_m integer, temporal_res interval,
  processing_method text NOT NULL, retrieved_at timestamptz,
  missing_pct real CHECK (missing_pct BETWEEN 0 AND 100),
  assumptions text[] NOT NULL DEFAULT '{}', limitations text[] NOT NULL DEFAULT '{}',
  evidence_rule_id text NOT NULL,
  CHECK ((provenance = 'desconocido') = (evidence_level IS NULL)));
