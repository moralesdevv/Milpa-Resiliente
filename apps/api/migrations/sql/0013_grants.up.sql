-- OWNER: R3. Mínimo privilegio para el rol de aplicación. :app_role se sustituye en la migración
-- (nombre validado con regex en migrations/_sql.py). El rol DEBE existir (infra/db/initdb o fixture
-- de pruebas) y debe ser NOSUPERUSER NOBYPASSRLS; el DO-block lo comprueba.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{app_role}') THEN
    RAISE EXCEPTION 'El rol de aplicación {app_role} no existe: créelo antes de migrar (infra/db/initdb/10-roles.sh)';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{app_role}' AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'El rol {app_role} no puede ser SUPERUSER ni BYPASSRLS (spec R3 §9.4)';
  END IF;
END $$;

GRANT USAGE ON SCHEMA auth, prov, ref, geo, farm, private, soil, econ, engine, report TO {app_role};
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA auth, farm, soil, report, prov TO {app_role};

-- auth
GRANT SELECT ON auth.app_user TO {app_role};
GRANT UPDATE (failed_login_count, last_failed_login_at, locked_until) ON auth.app_user TO {app_role};
GRANT SELECT, INSERT ON auth.consent TO {app_role};
GRANT UPDATE (withdrawn_at) ON auth.consent TO {app_role};
GRANT INSERT, SELECT ON auth.audit_log TO {app_role};
GRANT USAGE ON SEQUENCE auth.audit_log_audit_id_seq TO {app_role};

-- prov (R1): lectura; la API registra procedencia de mediciones/declaraciones de suelo
GRANT SELECT ON ALL TABLES IN SCHEMA prov TO {app_role};
GRANT INSERT, DELETE ON prov.indicator_provenance TO {app_role};

-- ref / econ (R1): solo lectura
GRANT SELECT ON ALL TABLES IN SCHEMA ref TO {app_role};
GRANT SELECT ON ALL TABLES IN SCHEMA econ TO {app_role};

-- geo (R1): lectura; POST /v1/zones inserta/actualiza zone
GRANT SELECT ON ALL TABLES IN SCHEMA geo TO {app_role};
GRANT INSERT, UPDATE ON geo.zone TO {app_role};

-- farm / private / soil / report (R3 con RLS)
GRANT SELECT, UPDATE ON farm.farmer TO {app_role};
GRANT SELECT, INSERT, UPDATE, DELETE ON farm.parcel, farm.parcel_history, farm.priority_profile TO {app_role};
GRANT SELECT, INSERT, UPDATE ON farm.technician_assignment TO {app_role};
GRANT SELECT, INSERT, UPDATE, DELETE ON private.parcel_geometry TO {app_role};
GRANT SELECT, INSERT, UPDATE, DELETE ON soil.sample, soil.measurement, soil.declaration TO {app_role};
GRANT SELECT ON soil.estimate, soil.property_status TO {app_role};
GRANT SELECT, INSERT, UPDATE, DELETE ON report.report TO {app_role};

-- engine: la API persiste lo que el motor devuelva (R2) y gestiona trabajos
GRANT SELECT, INSERT, UPDATE ON engine.job TO {app_role};
GRANT SELECT, INSERT, UPDATE, DELETE ON engine.analysis_run, engine.scenario_run, engine.risk_summary,
  engine.planting_summary, engine.ranking_result, engine.ranking_stability, engine.soil_voi_result TO {app_role};
GRANT SELECT ON engine.scenario_def TO {app_role};
