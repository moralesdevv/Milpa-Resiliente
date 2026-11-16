-- OWNER: R1 (provisional, ADR-003). README §13.3.
CREATE TABLE geo.region (
  region_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text UNIQUE NOT NULL, name text NOT NULL,
  config_uri text NOT NULL, config_hash char(64) NOT NULL, bbox geometry(Polygon,4326) NOT NULL);

CREATE TABLE geo.zone (
  zone_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), region_id uuid NOT NULL REFERENCES geo.region,
  name text NOT NULL, geom geometry(MultiPolygon,4326) NOT NULL,
  elevation_m real, slope_pct real, ip_elevation uuid REFERENCES prov.indicator_provenance,
  ready_at timestamptz);
CREATE INDEX zone_geom_gist ON geo.zone USING gist (geom);

CREATE TABLE geo.climate_cell (
  cell_id serial PRIMARY KEY, source_id smallint NOT NULL REFERENCES prov.data_source,
  centroid geometry(Point,4326) NOT NULL, footprint geometry(Polygon,4326) NOT NULL,
  UNIQUE (source_id, centroid));
CREATE INDEX climate_cell_footprint_gist ON geo.climate_cell USING gist (footprint);
CREATE TABLE geo.zone_cell (
  zone_id uuid REFERENCES geo.zone, cell_id int REFERENCES geo.climate_cell,
  weight real NOT NULL CHECK (weight > 0 AND weight <= 1), PRIMARY KEY (zone_id, cell_id));

-- C3: FK diferida de ref.strategy -> geo.region
ALTER TABLE ref.strategy ADD CONSTRAINT strategy_region_fk FOREIGN KEY (region_id) REFERENCES geo.region;
