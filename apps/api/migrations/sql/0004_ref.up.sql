-- OWNER: R1 (provisional, ADR-003). README §13.4 (soil_property) y §13.5.
-- C3: ref.strategy NO lleva FK a geo.region aquí (geo se migra después); se agrega en 0005_geo.
CREATE TABLE ref.soil_property (
  code text PRIMARY KEY, unit text NOT NULL, valid_min real, valid_max real,
  accepted_methods text[] NOT NULL, max_age_years smallint);

CREATE TABLE ref.catalog_release (
  catalog_release_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  catalog_hash char(64) UNIQUE NOT NULL, git_sha text NOT NULL, loaded_at timestamptz DEFAULT now());

CREATE TABLE ref.crop (
  crop_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text UNIQUE NOT NULL,
  name_es text NOT NULL, name_en text NOT NULL, scientific_name text, family text NOT NULL,
  is_legume boolean, fixes_n_conditions text);
CREATE TABLE ref.crop_variety (
  variety_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), crop_id uuid NOT NULL REFERENCES ref.crop,
  name text NOT NULL, phenology_basis text NOT NULL CHECK (phenology_basis IN ('days','gdd')),
  cycle_days int, gdd_base_c real, gdd_total real, fallow_kc real,
  citation_id int REFERENCES prov.citation, UNIQUE (crop_id, name));
CREATE TABLE ref.phenology_stage (
  variety_id uuid REFERENCES ref.crop_variety, stage_code text, seq smallint NOT NULL,
  length_days int, gdd_start real, gdd_end real, is_critical boolean NOT NULL DEFAULT false,
  kc_start real NOT NULL, kc_end real NOT NULL, citation_id int REFERENCES prov.citation,
  PRIMARY KEY (variety_id, stage_code));
CREATE TABLE ref.crop_root_param (
  variety_id uuid PRIMARY KEY REFERENCES ref.crop_variety, z_min_m real NOT NULL, z_max_m real NOT NULL,
  depletion_fraction_p real NOT NULL CHECK (depletion_fraction_p > 0 AND depletion_fraction_p < 1),
  citation_id int NOT NULL REFERENCES prov.citation);
CREATE TABLE ref.risk_threshold (
  threshold_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), crop_id uuid NOT NULL REFERENCES ref.crop,
  stage_code text NOT NULL,
  metric text NOT NULL CHECK (metric IN ('dekad_exposure_mm','stage_cum_exposure_mm','pef_over_etc_ratio','stress_days_equiv')),
  mode mode_t NOT NULL, peff_method text, value real NOT NULL, unit text NOT NULL,
  sens_low real NOT NULL, sens_high real NOT NULL, evidence_level evidence_t NOT NULL,
  citation_id int NOT NULL REFERENCES prov.citation);
CREATE TABLE ref.ph_tolerance (
  crop_id uuid PRIMARY KEY REFERENCES ref.crop, ph_abs_min real, ph_opt_min real, ph_opt_max real,
  ph_abs_max real, ph_method text NOT NULL, evidence_level evidence_t NOT NULL,
  citation_id int NOT NULL REFERENCES prov.citation);
CREATE TABLE ref.reference_yield (
  variety_id uuid REFERENCES ref.crop_variety, region_code text, management_level text,
  kg_per_ha real NOT NULL, evidence_level evidence_t NOT NULL,
  citation_id int NOT NULL REFERENCES prov.citation,
  PRIMARY KEY (variety_id, region_code, management_level));
CREATE TABLE ref.food_composition (
  crop_id uuid PRIMARY KEY REFERENCES ref.crop, kcal_per_kg real NOT NULL,
  protein_g_per_kg real NOT NULL, citation_id int NOT NULL REFERENCES prov.citation);

CREATE TABLE ref.strategy (
  strategy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), region_id uuid,
  code text UNIQUE NOT NULL, name text NOT NULL, is_reference boolean NOT NULL DEFAULT false,
  changes_from_reference strategy_axis_t[] NOT NULL DEFAULT '{}');
CREATE TABLE ref.strategy_version (
  strategy_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id uuid NOT NULL REFERENCES ref.strategy, version int NOT NULL,
  catalog_release_id uuid NOT NULL REFERENCES ref.catalog_release,
  horizon_years smallint NOT NULL CHECK (horizon_years >= 1),
  anchor_cycle_idx smallint NOT NULL DEFAULT 1, UNIQUE (strategy_id, version));
CREATE TABLE ref.strategy_cycle (
  strategy_version_id uuid REFERENCES ref.strategy_version,
  cycle_idx smallint CHECK (cycle_idx >= 1),
  agri_year_offset smallint NOT NULL CHECK (agri_year_offset >= 0), season text NOT NULL,
  window_mode window_mode_t NOT NULL, plant_window_start char(5), plant_window_end char(5),
  rel_lag_days smallint, fallow_after_days smallint NOT NULL DEFAULT 0,
  soil_carryover boolean NOT NULL DEFAULT false,
  PRIMARY KEY (strategy_version_id, cycle_idx));
CREATE TABLE ref.strategy_cycle_component (
  strategy_version_id uuid, cycle_idx smallint, variety_id uuid REFERENCES ref.crop_variety,
  role text NOT NULL CHECK (role IN ('principal','acompanante','cobertura')),
  area_fraction real NOT NULL CHECK (area_fraction > 0 AND area_fraction <= 1),
  plant_offset_days smallint NOT NULL DEFAULT 0,
  PRIMARY KEY (strategy_version_id, cycle_idx, variety_id),
  FOREIGN KEY (strategy_version_id, cycle_idx) REFERENCES ref.strategy_cycle);
CREATE TABLE ref.strategy_criteria (
  strategy_version_id uuid REFERENCES ref.strategy_version,
  criterion text CHECK (criterion IN ('soil','food','income')),
  sub_indicator text, value real, unit text, evidence_level evidence_t NOT NULL,
  citation_id int REFERENCES prov.citation,
  PRIMARY KEY (strategy_version_id, criterion, sub_indicator));
