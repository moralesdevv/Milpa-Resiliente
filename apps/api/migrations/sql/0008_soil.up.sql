-- OWNER: R1 tablas de suelo (provisional, ADR-003). La vista usa security_invoker (R3) para respetar RLS.
CREATE TABLE soil.sample (
  sample_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), parcel_id uuid NOT NULL REFERENCES farm.parcel,
  sampled_at date NOT NULL CHECK (sampled_at <= current_date), lab text,
  depth_from_cm smallint NOT NULL, depth_to_cm smallint NOT NULL CHECK (depth_to_cm > depth_from_cm),
  ingestion_id uuid REFERENCES prov.ingestion_run);
CREATE INDEX sample_parcel_idx ON soil.sample (parcel_id);

CREATE TABLE soil.measurement (
  measurement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sample_id uuid NOT NULL REFERENCES soil.sample, property_code text NOT NULL REFERENCES ref.soil_property,
  value real NOT NULL, unit text NOT NULL, method text NOT NULL,
  representativeness text NOT NULL CHECK (representativeness IN ('parcela','zona','otra_parcela','desconocida')),
  ip_id uuid NOT NULL REFERENCES prov.indicator_provenance,
  UNIQUE (sample_id, property_code));

CREATE TABLE soil.declaration (
  parcel_id uuid REFERENCES farm.parcel, property_code text REFERENCES ref.soil_property,
  value real NOT NULL, unit text NOT NULL, basis text NOT NULL, declared_by uuid REFERENCES auth.app_user,
  declared_at timestamptz NOT NULL DEFAULT now(), ip_id uuid NOT NULL REFERENCES prov.indicator_provenance,
  PRIMARY KEY (parcel_id, property_code));

CREATE TABLE soil.estimate (
  zone_id uuid REFERENCES geo.zone, property_code text REFERENCES ref.soil_property, depth_label text,
  value real, p05 real, p95 real, source_id smallint NOT NULL REFERENCES prov.data_source,
  ip_id uuid REFERENCES prov.indicator_provenance, reason text,
  PRIMARY KEY (zone_id, property_code, depth_label));

-- README §13.4 (corrige A07). security_invoker=true: sin esto la vista evadiría RLS (corre como propietario).
CREATE VIEW soil.property_status WITH (security_invoker = true) AS
WITH latest AS (
  SELECT DISTINCT ON (s.parcel_id, m.property_code) s.parcel_id, m.property_code, s.sampled_at, m.representativeness
  FROM soil.measurement m JOIN soil.sample s USING (sample_id)
  ORDER BY s.parcel_id, m.property_code, s.sampled_at DESC)
SELECT p.parcel_id, sp.code AS property_code,
  CASE
    WHEN l.property_code IS NOT NULL AND l.representativeness IN ('otra_parcela','desconocida') THEN 'no_representativo'
    WHEN l.property_code IS NOT NULL AND sp.max_age_years IS NOT NULL
         AND l.sampled_at < current_date - make_interval(years => sp.max_age_years)            THEN 'desactualizado'
    WHEN l.property_code IS NOT NULL                                                           THEN 'medido'
    WHEN d.property_code IS NOT NULL                                                           THEN 'declarado'
    WHEN e.value IS NOT NULL                                                                   THEN 'estimado'
    WHEN e.property_code IS NOT NULL                                                           THEN 'no_disponible'
    ELSE 'desconocido'
  END::property_status_t AS status
FROM farm.parcel p CROSS JOIN ref.soil_property sp
LEFT JOIN latest l ON l.parcel_id = p.parcel_id AND l.property_code = sp.code
LEFT JOIN soil.declaration d ON d.parcel_id = p.parcel_id AND d.property_code = sp.code
LEFT JOIN soil.estimate e ON e.zone_id = p.zone_id AND e.property_code = sp.code;
