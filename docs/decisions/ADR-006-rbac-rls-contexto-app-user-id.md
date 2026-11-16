# ADR-006: RBAC + RLS y contexto `app.user_id`

- **Fecha:** 2026-11-14 · **Estado:** aceptado

## Contexto
La autorización no puede depender solo del rol ni de la capa de aplicación: un endpoint con error no debe exponer filas ajenas.

## Decisión
1. **Capa de aplicación** (`AccessPolicy`): comprueba pertenencia (agricultor = dueño; técnico = asignación vigente + consentimiento `analysis` vigente; admin = sin acceso automático) y devuelve 404 si no es visible (anti-enumeración).
2. **RLS en PostgreSQL** sobre `farm.farmer/parcel/parcel_history/priority_profile/technician_assignment`, `private.parcel_geometry`, `soil.sample/measurement/declaration`, `report.report` (`soil.estimate` es zonal y público). Funciones auxiliares `SECURITY DEFINER` con `search_path` fijo evitan recursión entre políticas.
3. **Contexto:** `SET LOCAL app.user_id = '<uuid>'` dentro de la transacción de la solicitud (`UnitOfWork.set_user`); solo acepta `uuid.UUID` (sin inyección). `commit()/rollback()` reaplican el contexto explícitamente; sin contexto, RLS no devuelve filas (falla segura). El pool usa `reset_on_return="rollback"`.
4. **Rol de aplicación** `milpa_app`: `NOSUPERUSER NOBYPASSRLS`, **no propietario** de tablas, con privilegios mínimos por tabla (`0013_grants`). Las migraciones usan otro rol (propietario). La vista `soil.property_status` usa `security_invoker=true` (si no, evadiría RLS).

## Alternativas
Solo filtros en consultas (frágil), un rol propietario con `FORCE RLS` (complica funciones auxiliares), claims en `current_setting` firmados (innecesario).

## Consecuencias / riesgos
(+) Doble barrera verificada con dos usuarios en `tests/integration/test_rls.py`, incluida la no filtración entre transacciones en una misma conexión. (−) `SECURITY DEFINER` exige revisar cada función. Riesgo: olvidar `set_user` en un camino nuevo → mitigado por la falla segura y por `CtxDep` como única vía de acceso a servicios.

**Aprobadores:** R3 + responsable de seguridad.
