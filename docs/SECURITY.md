# Seguridad (R3)

> Estado honesto: los controles descritos están **implementados y probados** donde se indica. Esto no equivale a afirmar que el sistema sea seguro: no hay auditoría externa, revisión legal ni prueba de penetración (ver §6).

## 1. Modelo de amenazas (resumen)
| Amenaza | Control | Prueba |
|---|---|---|
| Acceso a parcelas/suelo/informes ajenos | autorización por pertenencia (`AccessPolicy`) **+ RLS** con el rol real; 404 uniforme (anti-enumeración) | `test_rls.py` (dos+ usuarios), `test_api_parcels.py`, `test_api_analysis.py` |
| Escalada por rol en el token | el rol efectivo se lee de la BD, no del JWT | `test_role_comes_from_database_not_from_token` |
| Fuerza bruta / enumeración de cuentas | Argon2id, bloqueo progresivo, mismo 401 y mensaje, hash ficticio, límite de tasa por IP y usuario | `test_api_auth.py` |
| JWT forjado/expirado/otra audiencia/`alg=none` | HS256 fijo, claims obligatorios, `iss/aud/exp/jti` | `test_token_with_wrong_signature_alg_none_or_audience_is_rejected` |
| Contexto RLS filtrado entre solicitudes | `SET LOCAL` solo por transacción, reaplicado tras commit/rollback, `pool_reset_on_return=rollback`, falla segura | `test_context_does_not_leak_*` |
| Evasión de RLS por el rol de la app | rol no propietario, sin BYPASSRLS, migración aborta si lo tiene; vista `security_invoker` | `test_application_role_cannot_bypass_rls`, `test_property_status_view_is_security_invoker` |
| Inyección SQL | consultas parametrizadas; `SET LOCAL` solo con `uuid.UUID` tipado | `test_sql_injection_through_user_id_is_impossible` |
| CSV malicioso / DoS | `text/csv` por streaming con tope (413), 415, UTF-8 estricto, ≤5000 filas/64 columnas/200 caracteres, errores sin repetir valores, todo-o-nada; neutralización de fórmulas al exportar | `test_storage_hashing_csv.py`, `test_api_parcels.py` |
| SSRF / lectura de archivos vía PDF | `url_fetcher` solo `data:`; CSS incrustado; `base_url=None`; Jinja2 sandbox + autoescape | `test_reports.py` (SSRF, en Docker) |
| Path traversal en almacenamiento | `LocalObjectStore.resolve` (segmentos validados, symlinks resueltos) | `test_storage_hashing_csv.py` |
| Fuga en logs/errores | JSON con redacción (correo, coordenadas >3 decimales, JWT/Bearer, hashes, `usuario:clave@`, query strings), sin cuerpos, `hide_parameters`, 500 genérico | `tests/privacy/test_privacy_leaks.py` |
| Manipulación de PDF almacenado | SHA-256 verificado en cada descarga | `test_report_download_verifies_hash_and_access` |
| CORS abierto | lista explícita; `*` rechazado al arrancar | `test_cors_is_restrictive_by_default…` |
| Secretos en el repositorio/imagen | solo entorno; `.env.example` vacío; gitleaks en CI; prueba de patrones | `test_env_example_and_docker_files_have_no_secrets` |
| Dependencias vulnerables | `uv.lock` fijo + `pip-audit` en CI | CI |

## 2. Autenticación y autorización
Ver ADR-005/006. JWT de 15 min por defecto (≤120). Sin *refresh*. Rotación con `JWT_SECRET_PREVIOUS`. Roles: `tecnico`, `agricultor`, `admin` (el admin **no** accede a contenido privado; la vía de acceso excepcional registrado no existe todavía → ADR-015).

### Guardia de arranque (invariantes de la base)
`api.db.invariants` comprueba al arrancar que: el rol de la aplicación no es superusuario ni tiene BYPASSRLS; las 10 tablas con filas privadas (`farm.*`, `private.parcel_geometry`, `report.report`, `soil.sample/measurement/declaration`) tienen RLS activa; y **toda vista** de los esquemas de datos usa `security_invoker`. Si no, el servicio **se niega a arrancar** (falla cerrado). Origen: el script `92_soil_fixture_provenance.sql` de R1 recrea `soil.property_status` sin esa opción y, medido, un usuario sin parcelas veía las filas de parcelas ajenas (`docs/auditoria/matriz_compatibilidad.md`, S-01). No cubre funciones `SECURITY DEFINER` nuevas ni otros DDL ajenos.

## 3. Cabeceras y red
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` (salvo ETag/PDF privados). TLS/HSTS/CSP los aporta el proxy del host (README §22). La BD no publica puertos.

## 4. Contenedores
Usuario `10001`, `cap_drop: ALL`, `no-new-privileges`, sin secretos en capas, `MIGRATION_DATABASE_URL` eliminado del entorno antes de lanzar la API.

## 5. Registro de eventos
`auth.audit_log` guarda solo `actor_user_id`, acción, tipo/id de recurso y fecha (borrado de parcela, consentimiento, asignación). Nunca contenido personal.

## 6. Limitaciones conocidas / no cubierto
- Limitador de tasa y pool de trabajos **por proceso** (una réplica).
- Tokens no revocables antes de expirar.
- Sin 2FA, sin política de contraseñas más allá de longitud 12–256.
- Retención de registros y de copias de seguridad: pendiente (DP-13).
- Sin pruebas de penetración ni revisión legal. Escáner de secretos y `pip-audit` corren en CI (no se afirma resultado limpio fuera de lo reportado en `docs/TESTING.md`).
- **Credenciales del propietario en Compose:** `MIGRATION_DATABASE_URL` se elimina del entorno del proceso uvicorn, pero sigue en la *configuración* del contenedor (`docker inspect`, `docker compose exec`). En producción use `RUN_MIGRATIONS=false` y migre con una ejecución puntual, o inyecte la URL como secreto de la plataforma.
- Tamaño de cuerpo JSON se limita por `Content-Length` (1 MiB); un cliente que envíe *chunked* sin longitud no queda acotado a nivel de aplicación (mitigar en el proxy).
