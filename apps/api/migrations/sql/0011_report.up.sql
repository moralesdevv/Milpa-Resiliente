-- OWNER: R3. README §13.6.
CREATE TABLE report.report (
  report_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid REFERENCES engine.analysis_run, ranking_id uuid REFERENCES engine.ranking_result,
  locale text CHECK (locale IN ('es','es+en')), template_version text,
  privacy_level text NOT NULL CHECK (privacy_level IN ('internal','public')),
  content_json jsonb NOT NULL, pdf_uri text, pdf_sha256 char(64),
  generated_by uuid REFERENCES auth.app_user, generated_at timestamptz DEFAULT now());
CREATE INDEX report_run_idx ON report.report (run_id);
CREATE INDEX report_generated_by_idx ON report.report (generated_by);
