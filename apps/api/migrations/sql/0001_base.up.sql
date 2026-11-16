-- OWNER: R3 (infraestructura). Extensiones, esquemas y tipos (README §13.1).
-- Los enums científicos tienen fuente canónica en milpa_core.enums (R2); este DDL es la
-- contraparte SQL y se verifica por paridad (tests/contract/test_enum_parity.py).
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA auth;
CREATE SCHEMA prov;
CREATE SCHEMA ref;
CREATE SCHEMA geo;
CREATE SCHEMA farm;
CREATE SCHEMA private;
CREATE SCHEMA soil;
CREATE SCHEMA econ;
CREATE SCHEMA engine;
CREATE SCHEMA report;

CREATE TYPE provenance_t        AS ENUM ('medido','satelital','estimado','modelado','declarado','desconocido');
CREATE TYPE evidence_t          AS ENUM ('A','B','C');
CREATE TYPE property_status_t   AS ENUM ('medido','estimado','declarado','desconocido','desactualizado','no_representativo','no_disponible');
CREATE TYPE mode_t              AS ENUM ('exposure','root_zone');
CREATE TYPE label_t             AS ENUM ('indicador_exposicion_climatica','balance_hidrico_zona_radicular');
CREATE TYPE cell_state_t        AS ENUM ('critical','non_critical','insufficient_data','not_evaluable');
CREATE TYPE criterion_status_t  AS ENUM ('evaluable','provisional','not_evaluable');
CREATE TYPE ranking_status_t    AS ENUM ('ok','insufficient');
CREATE TYPE stability_flag_t    AS ENUM ('stable','moderate','unstable','insufficient');
CREATE TYPE voi_applicability_t AS ENUM ('evaluable','already_measured','not_applicable');
CREATE TYPE voi_outcome_t       AS ENUM ('ranking_stable','ranking_sensitive','insufficient_info');
CREATE TYPE adaptation_t        AS ENUM ('none','onset_rule');
CREATE TYPE humidity_t          AS ENUM ('not_applicable','constant_rh','constant_ea');
CREATE TYPE strategy_axis_t     AS ENUM ('association','rotation','planting_date','variety','cover_crop');
CREATE TYPE window_mode_t       AS ENUM ('candidate_dates','fixed_season_window','relative_to_previous_harvest');
CREATE TYPE user_role_t         AS ENUM ('tecnico','agricultor','admin');
CREATE TYPE job_status_t        AS ENUM ('queued','running','ok','failed','cancelled');
