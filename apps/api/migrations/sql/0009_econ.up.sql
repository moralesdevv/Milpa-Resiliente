-- OWNER: R1 (provisional, ADR-003). README §13.4.
CREATE TABLE econ.price_record (
  price_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), crop_id uuid NOT NULL REFERENCES ref.crop,
  zone_id uuid REFERENCES geo.zone, value numeric NOT NULL, unit text NOT NULL, currency char(3) NOT NULL,
  market text NOT NULL, observed_on date NOT NULL, source text NOT NULL,
  ip_id uuid REFERENCES prov.indicator_provenance);
CREATE TABLE econ.cost_record (
  cost_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), strategy_id uuid, item text NOT NULL,
  kind text CHECK (kind IN ('variable','fixed')), value numeric NOT NULL, unit text NOT NULL,
  currency char(3) NOT NULL, observed_on date NOT NULL, source text NOT NULL);
