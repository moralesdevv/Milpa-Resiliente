-- OWNER: R3. README §13.3 (sin geometría exacta).
CREATE TABLE farm.farmer (
  farmer_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid REFERENCES auth.app_user,
  display_name text NOT NULL, community text, language text NOT NULL DEFAULT 'es',
  household_size smallint,
  created_at timestamptz NOT NULL DEFAULT now());                       -- R3-EXT
CREATE UNIQUE INDEX farmer_user_unique ON farm.farmer (user_id) WHERE user_id IS NOT NULL;  -- R3-EXT

CREATE TABLE farm.parcel (
  parcel_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), zone_id uuid NOT NULL REFERENCES geo.zone,
  farmer_id uuid REFERENCES farm.farmer, code text, area_ha numeric(8,2),
  display_geom geometry(Point,4326),
  display_grid_m integer CHECK (display_grid_m >= 1000),
  created_at timestamptz NOT NULL DEFAULT now(),                        -- R3-EXT
  created_by uuid REFERENCES auth.app_user);                            -- R3-EXT
CREATE INDEX parcel_zone_idx ON farm.parcel (zone_id);
CREATE INDEX parcel_farmer_idx ON farm.parcel (farmer_id);
CREATE INDEX parcel_display_geom_gist ON farm.parcel USING gist (display_geom);

CREATE TABLE farm.parcel_history (
  parcel_id uuid REFERENCES farm.parcel, cycle_year smallint, season text,
  variety_id uuid REFERENCES ref.crop_variety, planting_date date, harvest_date date,
  source text NOT NULL CHECK (source IN ('declarado','detectado_satelite')),
  ip_id uuid REFERENCES prov.indicator_provenance,
  PRIMARY KEY (parcel_id, cycle_year, season, variety_id));

CREATE TABLE farm.priority_profile (
  profile_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), parcel_id uuid REFERENCES farm.parcel,
  w_water numeric(4,3) NOT NULL, w_soil numeric(4,3) NOT NULL, w_food numeric(4,3) NOT NULL,
  w_income numeric(4,3) NOT NULL,
  constraints jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now(),                        -- R3-EXT
  CHECK (abs(w_water + w_soil + w_food + w_income - 1) < 0.001));
CREATE UNIQUE INDEX priority_profile_parcel_unique ON farm.priority_profile (parcel_id);  -- R3-EXT

CREATE TABLE farm.technician_assignment (
  technician_id uuid REFERENCES auth.app_user, farmer_id uuid REFERENCES farm.farmer,
  consent_id uuid NOT NULL REFERENCES auth.consent,
  assigned_at timestamptz NOT NULL DEFAULT now(), revoked_at timestamptz,
  PRIMARY KEY (technician_id, farmer_id));
