-- OWNER: R3. README §13.3. Opt-in nivel B; desactivada (ENABLE_EXACT_GEOMETRY=false). RLS en 0012.
CREATE TABLE private.parcel_geometry (
  parcel_id uuid PRIMARY KEY REFERENCES farm.parcel, exact_geom geometry(Polygon,4326) NOT NULL,
  consent_id uuid NOT NULL REFERENCES auth.consent);
