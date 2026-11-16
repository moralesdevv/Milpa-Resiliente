-- OWNER: R1 (datos de referencia), aplicado por la cadena Alembic única de R3 (ADR-003/018).
-- Origen: references/Milpa-Resiliente-R1/sql/{90_seed,91_seed_soil,93_seed_imerg}.sql + la fuente de
-- fixtures de 92_soil_fixture_provenance.sql. NO se incluye la sustitución de la vista
-- soil.property_status de 92: eliminaba `security_invoker` y evadía RLS (docs/auditoria S-01).
-- Idempotente. IDs fijos para que sean reproducibles entre entornos.

INSERT INTO prov.data_source (source_id, code, product_name, institution, is_nasa, temporal_res, access_url)
VALUES (1, 'POWER_DAILY', 'NASA POWER diario (comunidad AG)', 'NASA (reanálisis MERRA-2 y CERES)', true,
        interval '1 day', 'https://power.larc.nasa.gov/')
ON CONFLICT DO NOTHING;

-- license vacío a propósito: se llena tras leer los términos oficiales (DE-12/DP-14); no redistribuible
INSERT INTO prov.data_source (source_id, code, product_name, institution, is_nasa, version, spatial_res_m,
                              temporal_res, redistributable, access_url)
VALUES (2, 'IMERG_FINAL_V07', 'GPM IMERG Final Run diario, 0.1° (GPM_3IMERGDF)', 'NASA GES DISC', true, '07',
        10000, interval '1 day', false, 'https://doi.org/10.5067/GPM/IMERGDF/DAY/07')
ON CONFLICT DO NOTHING;

INSERT INTO prov.data_source (source_id, code, product_name, institution, is_nasa, version, license,
                              redistributable, access_url)
VALUES (3, 'SOIL_CSV_FIXTURE', 'CSV sintético de propiedades del suelo', 'Datos sintéticos internos', false,
        'fixture-1', 'Uso interno de pruebas', false, NULL)
ON CONFLICT DO NOTHING;

INSERT INTO ref.soil_property (code, unit, valid_min, valid_max, accepted_methods, max_age_years) VALUES
  ('ph',              'pH',      3,    10,   ARRAY['H2O_1:2.5', 'CaCl2_1:2'], NULL),
  ('organic_matter',  '%',       0,    100,  ARRAY['Walkley-Black'],          NULL),
  ('sand',            '%',       0,    100,  ARRAY['hidrometro'],             NULL),
  ('silt',            '%',       0,    100,  ARRAY['hidrometro'],             NULL),
  ('clay',            '%',       0,    100,  ARRAY['hidrometro'],             NULL),
  ('cec',             'cmol/kg', 0,    200,  ARRAY['acetato_amonio'],         NULL),
  ('effective_depth', 'cm',      0,    1000, ARRAY['declarado/medido'],       NULL),
  ('awc',             'mm/m',    0,    400,  ARRAY['placa_presion'],          NULL)
ON CONFLICT (code) DO NOTHING;
