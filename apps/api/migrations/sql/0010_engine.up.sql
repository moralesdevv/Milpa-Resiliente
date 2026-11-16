-- OWNER: engine.job -> R3; resto de engine.* -> estructura README §13.6 (semántica científica: R2).
-- R3 solo persiste/transporta; no define contenido científico.
CREATE TABLE engine.analysis_run (
  run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), zone_id uuid NOT NULL REFERENCES geo.zone,
  parcel_id uuid REFERENCES farm.parcel,
  period_start date NOT NULL, period_end date NOT NULL,
  mode mode_t NOT NULL, mode_reasons text[] NOT NULL DEFAULT '{}',
  params jsonb NOT NULL, params_hash char(64) NOT NULL,
  region_config_hash char(64) NOT NULL, catalog_release_id uuid NOT NULL REFERENCES ref.catalog_release,
  data_hash char(64) NOT NULL, code_version text NOT NULL, seed bigint NOT NULL,
  created_by uuid REFERENCES auth.app_user, created_at timestamptz DEFAULT now(),
  status text NOT NULL CHECK (status IN ('queued','running','ok','failed')));
CREATE INDEX analysis_run_zone_idx ON engine.analysis_run (zone_id);
CREATE INDEX analysis_run_parcel_idx ON engine.analysis_run (parcel_id);
ALTER TABLE prov.indicator_provenance ADD FOREIGN KEY (run_id) REFERENCES engine.analysis_run;

CREATE TABLE engine.scenario_def (
  scenario_id text PRIMARY KEY,
  delta_t_c real NOT NULL, precip_factor real NOT NULL, onset_delay_days smallint NOT NULL,
  humidity_assumption humidity_t NOT NULL,
  grid_role text NOT NULL CHECK (grid_role IN ('baseline','primary_grid','humidity_sensitivity')),
  method_doc text NOT NULL, label text NOT NULL DEFAULT 'escenario sintético',
  CHECK ((delta_t_c = 0) = (humidity_assumption = 'not_applicable')));

CREATE TABLE engine.scenario_run (
  run_id uuid REFERENCES engine.analysis_run, scenario_id text REFERENCES engine.scenario_def,
  adaptation_mode adaptation_t,
  status text NOT NULL, results_uri text NOT NULL, results_sha256 char(64), n_rows bigint,
  engine_version text NOT NULL, executed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, scenario_id, adaptation_mode));

CREATE TABLE engine.risk_summary (
  run_id uuid, scenario_id text, adaptation_mode adaptation_t,
  strategy_version_id uuid REFERENCES ref.strategy_version,
  level text NOT NULL CHECK (level IN ('cycle','strategy')), cycle_idx smallint NOT NULL,
  n_valid smallint NOT NULL, n_expected smallint NOT NULL, n_decided smallint NOT NULL, coverage_pct real,
  freq_critical_pct real, severity_median real, severity_p90 real, severity_cvar90 real,
  worst_year smallint, worst_year_severity real, tail_ratio real,
  horizon_years smallint NOT NULL, overlapping_cohorts boolean NOT NULL,
  threshold_sensitivity jsonb, peff_sensitivity jsonb, consistency text, unit text NOT NULL,
  label label_t NOT NULL, provisional boolean NOT NULL, reason text,
  ip_id uuid REFERENCES prov.indicator_provenance,
  PRIMARY KEY (run_id, scenario_id, adaptation_mode, strategy_version_id, level, cycle_idx),
  FOREIGN KEY (run_id, scenario_id, adaptation_mode) REFERENCES engine.scenario_run,
  CHECK ((level = 'strategy') = (cycle_idx = 0)));

CREATE TABLE engine.planting_summary (
  run_id uuid, scenario_id text, adaptation_mode adaptation_t, strategy_version_id uuid,
  view text CHECK (view IN ('cycle','strategy')), cycle_idx smallint, plant_md char(5),
  n_decided smallint, n_valid smallint, pct_critical real, severity_median real, severity_p90 real,
  PRIMARY KEY (run_id, scenario_id, adaptation_mode, strategy_version_id, view, cycle_idx, plant_md),
  FOREIGN KEY (run_id, scenario_id, adaptation_mode) REFERENCES engine.scenario_run);

CREATE TABLE engine.ranking_result (
  ranking_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL,
  scenario_id text NOT NULL, adaptation_mode adaptation_t NOT NULL,
  status ranking_status_t NOT NULL, missing_policy text NOT NULL, criteria_used text[] NOT NULL,
  weights jsonb NOT NULL, weights_effective jsonb, weight_coverage real,
  scores jsonb, total jsonb, order_ids uuid[], top_margin real, margin_within_uncertainty boolean,
  evidence evidence_t, provisional boolean NOT NULL, decision_log jsonb NOT NULL, eligibility jsonb NOT NULL,
  FOREIGN KEY (run_id, scenario_id, adaptation_mode) REFERENCES engine.scenario_run);

CREATE TABLE engine.ranking_stability (
  stability_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ranking_id uuid NOT NULL REFERENCES engine.ranking_result,
  n_samples int NOT NULL, mode text NOT NULL, concentration real, radius real, seed bigint NOT NULL,
  stable_share real NOT NULL, unstable_share real NOT NULL,
  top1_share jsonb, rank_corr_mean real, flag stability_flag_t NOT NULL, conflict jsonb);

CREATE TABLE engine.soil_voi_result (
  voi_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid REFERENCES engine.analysis_run,
  parcel_id uuid REFERENCES farm.parcel,
  property_code text NOT NULL REFERENCES ref.soil_property, property_status property_status_t NOT NULL,
  applicability voi_applicability_t NOT NULL, outcome voi_outcome_t, lab_recommended boolean NOT NULL,
  hypotheticals jsonb, top_by_hypothetical jsonb, eligibility_changes jsonb,
  range_citation_id int REFERENCES prov.citation, rationale text NOT NULL,
  CHECK ((applicability = 'evaluable') = (outcome IS NOT NULL)));

-- R3-EXT (ADR-007, pendiente de aprobación): se añaden parcel_delete y consent_purge a los 4 tipos
-- de la especificación porque el borrado de parcela y la limpieza por retirada de consentimiento
-- deben ejecutarse como trabajo (spec R3 §4.4 / §9.7) y no existe un tipo que los represente.
CREATE TABLE engine.job (
  job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL CHECK (kind IN ('zone_ingest','analysis_run','scenario_run','report','parcel_delete','consent_purge')),
  status job_status_t NOT NULL DEFAULT 'queued',
  progress real CHECK (progress IS NULL OR (progress >= 0 AND progress <= 1)),
  payload jsonb NOT NULL, result jsonb, error jsonb,
  idempotency_key text UNIQUE, attempts smallint NOT NULL DEFAULT 0,
  created_by uuid REFERENCES auth.app_user,
  created_at timestamptz DEFAULT now(), started_at timestamptz, finished_at timestamptz);
CREATE INDEX job_status_idx ON engine.job (status);
CREATE INDEX job_created_by_idx ON engine.job (created_by);
