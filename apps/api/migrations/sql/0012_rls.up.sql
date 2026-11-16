-- OWNER: R3. Row-Level Security (spec R3 §9.4, README §22).
-- Diseño:
--  * El rol de la aplicación NO es propietario y NO tiene BYPASSRLS (verificado en pruebas).
--  * app.user_id se fija con SET LOCAL por transacción; sin contexto => ninguna fila privada.
--  * Las funciones auxiliares son SECURITY DEFINER (propietario = rol de migración, que no está
--    sujeto a RLS) para evitar recursión entre políticas; fijan search_path.

CREATE FUNCTION auth.current_user_id() RETURNS uuid
  LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;

CREATE FUNCTION farm.is_farmer_owner(p_farmer uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT EXISTS (SELECT 1 FROM farm.farmer f
                 WHERE f.farmer_id = p_farmer AND f.user_id = auth.current_user_id())
$$;

-- Técnico: asignación vigente + consentimiento 'analysis' del agricultor no retirado.
CREATE FUNCTION farm.technician_assigned(p_farmer uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT EXISTS (
    SELECT 1 FROM farm.technician_assignment a
      JOIN farm.farmer f ON f.farmer_id = a.farmer_id
      JOIN auth.consent c ON c.consent_id = a.consent_id
    WHERE a.farmer_id = p_farmer AND a.technician_id = auth.current_user_id()
      AND a.revoked_at IS NULL AND c.withdrawn_at IS NULL
      AND c.purpose = 'analysis' AND c.subject_user_id = f.user_id)
$$;

CREATE FUNCTION farm.can_access_farmer(p_farmer uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT p_farmer IS NOT NULL AND (farm.is_farmer_owner(p_farmer) OR farm.technician_assigned(p_farmer))
$$;

CREATE FUNCTION farm.can_access_parcel(p_parcel uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT COALESCE((SELECT farm.can_access_farmer(p.farmer_id) FROM farm.parcel p WHERE p.parcel_id = p_parcel), false)
$$;

CREATE FUNCTION farm.is_parcel_owner(p_parcel uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT COALESCE((SELECT farm.is_farmer_owner(p.farmer_id) FROM farm.parcel p WHERE p.parcel_id = p_parcel), false)
$$;

-- Conjuntos visibles: se evalúan UNA vez por consulta (subplan no correlacionado). Las funciones
-- escalares anteriores se evalúan por fila y eran ~0,5 ms/fila (medido en BE-11): se conservan para
-- DELETE/INSERT puntuales y para prov.can_access_ip, pero las políticas de lectura usan estas.
CREATE FUNCTION farm.visible_farmers() RETURNS SETOF uuid
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT f.farmer_id FROM farm.farmer f WHERE f.user_id = auth.current_user_id()
  UNION
  SELECT a.farmer_id FROM farm.technician_assignment a
    JOIN farm.farmer f ON f.farmer_id = a.farmer_id
    JOIN auth.consent c ON c.consent_id = a.consent_id
  WHERE a.technician_id = auth.current_user_id() AND a.revoked_at IS NULL
    AND c.withdrawn_at IS NULL AND c.purpose = 'analysis' AND c.subject_user_id = f.user_id
$$;

CREATE FUNCTION farm.visible_parcels() RETURNS SETOF uuid
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT p.parcel_id FROM farm.parcel p WHERE p.farmer_id IN (SELECT farm.visible_farmers())
$$;

-- ---------------------------------------------------------------- farm
ALTER TABLE farm.farmer ENABLE ROW LEVEL SECURITY;
CREATE POLICY farmer_select ON farm.farmer FOR SELECT USING (farmer_id IN (SELECT farm.visible_farmers()));
CREATE POLICY farmer_update ON farm.farmer FOR UPDATE
  USING (farm.is_farmer_owner(farmer_id)) WITH CHECK (farm.is_farmer_owner(farmer_id));

ALTER TABLE farm.parcel ENABLE ROW LEVEL SECURITY;
CREATE POLICY parcel_select ON farm.parcel FOR SELECT USING (farmer_id IN (SELECT farm.visible_farmers()));
CREATE POLICY parcel_insert ON farm.parcel FOR INSERT WITH CHECK (farmer_id IN (SELECT farm.visible_farmers()));
CREATE POLICY parcel_update ON farm.parcel FOR UPDATE
  USING (farmer_id IN (SELECT farm.visible_farmers())) WITH CHECK (farmer_id IN (SELECT farm.visible_farmers()));
CREATE POLICY parcel_delete ON farm.parcel FOR DELETE USING (farm.is_farmer_owner(farmer_id));

ALTER TABLE farm.parcel_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY parcel_history_all ON farm.parcel_history FOR ALL
  USING (parcel_id IN (SELECT farm.visible_parcels())) WITH CHECK (parcel_id IN (SELECT farm.visible_parcels()));

ALTER TABLE farm.priority_profile ENABLE ROW LEVEL SECURITY;
CREATE POLICY priority_profile_all ON farm.priority_profile FOR ALL
  USING (parcel_id IN (SELECT farm.visible_parcels())) WITH CHECK (parcel_id IN (SELECT farm.visible_parcels()));

ALTER TABLE farm.technician_assignment ENABLE ROW LEVEL SECURITY;
CREATE POLICY assignment_select ON farm.technician_assignment FOR SELECT
  USING (technician_id = auth.current_user_id() OR farm.is_farmer_owner(farmer_id));
CREATE POLICY assignment_owner_write ON farm.technician_assignment FOR ALL
  USING (farm.is_farmer_owner(farmer_id)) WITH CHECK (farm.is_farmer_owner(farmer_id));

-- ---------------------------------------------------------------- private
ALTER TABLE private.parcel_geometry ENABLE ROW LEVEL SECURITY;
CREATE POLICY parcel_geometry_owner ON private.parcel_geometry FOR ALL
  USING (farm.is_parcel_owner(parcel_id)) WITH CHECK (farm.is_parcel_owner(parcel_id));

-- ---------------------------------------------------------------- soil (soil.estimate es zonal/público)
ALTER TABLE soil.sample ENABLE ROW LEVEL SECURITY;
CREATE POLICY sample_all ON soil.sample FOR ALL
  USING (parcel_id IN (SELECT farm.visible_parcels())) WITH CHECK (parcel_id IN (SELECT farm.visible_parcels()));
ALTER TABLE soil.measurement ENABLE ROW LEVEL SECURITY;
CREATE POLICY measurement_all ON soil.measurement FOR ALL
  USING (sample_id IN (SELECT sample_id FROM soil.sample))
  WITH CHECK (sample_id IN (SELECT sample_id FROM soil.sample));
ALTER TABLE soil.declaration ENABLE ROW LEVEL SECURITY;
CREATE POLICY declaration_all ON soil.declaration FOR ALL
  USING (parcel_id IN (SELECT farm.visible_parcels())) WITH CHECK (parcel_id IN (SELECT farm.visible_parcels()));

-- ---------------------------------------------------------------- report
ALTER TABLE report.report ENABLE ROW LEVEL SECURITY;
CREATE POLICY report_select ON report.report FOR SELECT
  USING (generated_by = auth.current_user_id()
         OR run_id IN (SELECT r.run_id FROM engine.analysis_run r WHERE r.parcel_id IN (SELECT farm.visible_parcels())));
CREATE POLICY report_insert ON report.report FOR INSERT
  WITH CHECK (generated_by = auth.current_user_id());
CREATE POLICY report_update ON report.report FOR UPDATE
  USING (generated_by = auth.current_user_id()
         OR run_id IN (SELECT r.run_id FROM engine.analysis_run r WHERE r.parcel_id IN (SELECT farm.visible_parcels())))
  WITH CHECK (generated_by = auth.current_user_id()
         OR run_id IN (SELECT r.run_id FROM engine.analysis_run r WHERE r.parcel_id IN (SELECT farm.visible_parcels())));
CREATE POLICY report_delete ON report.report FOR DELETE
  USING (generated_by = auth.current_user_id()
         OR run_id IN (SELECT r.run_id FROM engine.analysis_run r WHERE r.parcel_id IN (SELECT farm.visible_parcels())));

-- ---------------------------------------------------------------- procedencia (prov)
-- prov.indicator_provenance no es privada en sí, pero las filas que describen mediciones,
-- declaraciones, historial o resultados de una PARCELA solo deben ser visibles a quien accede a la
-- parcela. SECURITY DEFINER para ver las referencias aunque RLS las oculte al invocador.
CREATE FUNCTION prov.can_access_ip(p_ip uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT CASE
    WHEN auth.current_user_id() IS NULL THEN false
    WHEN EXISTS (SELECT 1 FROM soil.measurement m WHERE m.ip_id = p_ip) THEN
      EXISTS (SELECT 1 FROM soil.measurement m JOIN soil.sample s USING (sample_id)
              WHERE m.ip_id = p_ip AND farm.can_access_parcel(s.parcel_id))
    WHEN EXISTS (SELECT 1 FROM soil.declaration d WHERE d.ip_id = p_ip) THEN
      EXISTS (SELECT 1 FROM soil.declaration d WHERE d.ip_id = p_ip AND farm.can_access_parcel(d.parcel_id))
    WHEN EXISTS (SELECT 1 FROM farm.parcel_history h WHERE h.ip_id = p_ip) THEN
      EXISTS (SELECT 1 FROM farm.parcel_history h WHERE h.ip_id = p_ip AND farm.can_access_parcel(h.parcel_id))
    WHEN EXISTS (SELECT 1 FROM prov.indicator_provenance i JOIN engine.analysis_run r ON r.run_id = i.run_id
                 WHERE i.ip_id = p_ip AND r.parcel_id IS NOT NULL) THEN
      EXISTS (SELECT 1 FROM prov.indicator_provenance i JOIN engine.analysis_run r ON r.run_id = i.run_id
              WHERE i.ip_id = p_ip AND farm.can_access_parcel(r.parcel_id))
    ELSE true
  END
$$;
