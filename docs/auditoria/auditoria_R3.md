# Auditoría de R3 — Backend y plataforma (FASE 2-3)

Artefacto auditado: `apps/api` + `tests/` + `docs/` (esta sesión), contra `Especificacion_Tecnica_MILPA_R3.md` (requisitos R3-F01…F22), `README.md` y los entregables reales de R1 y R4. Es una **autoauditoría**: el mismo equipo revisa su trabajo; por eso cada afirmación remite a una prueba ejecutada o a un comando reproducible (`informe_validacion.md`).

> R3 **no es una estrategia agronómica**: es el backend. No contiene ni debe contener ciencia (CLAUDE.md §2 y §5). Su fidelidad se mide por: no duplicar `milpa_core`, transportar procedencia sin alterarla, respetar contratos de la especificación y privacidad.

## 1. Defectos de R3 hallados por esta auditoría (y corregidos)

| ID | Defecto | Cómo se detectó | Corrección | Prueba |
|---|---|---|---|---|
| C-15 | El contrato de CSV de suelo de R3 (`SOIL_CSV_V0_PROVISIONAL`: `sampled_at`, `representativeness`, `<propiedad>`) **se apartaba del que fija el README §9** (`parcel_code,sample_date,…,om_pct,…`) y que R1 ya cumple. R3 lo había declarado «pendiente de R1». | Aplicar el validador de R3 a los CSV reales de R1: rechazó los 4 | Reescrito como `SOIL_CSV_V1`: columnas fijas, `parcel_code` = código de la parcela destino, textura 100 ± 2, método por propiedad (`texture_method` compartido), `effective_root_depth_cm` con método `declarado/medido`, rechazo de coma decimal y de inyección de fórmulas | `test_storage_hashing_csv.py` (bloque CSV reescrito y ampliado), `test_r1_artifacts.py` (R1 válidos aceptados, 9 inválidos rechazados con su error) |
| — | `ProvenanceOut` usaba nombres de columnas de BD, no los del `ProvenanceInfo` del §15 | Comparar con el borrador de R4 (que sigue el §15) | `evidence`, `evidence_rule`, `method`, `period{start,end}`, `spatial_res`, `temporal_res`; se conservan `ip_id`, `indicator_code`, `unit` | `test_provenance_has_the_shape_of_the_spec_provenance_info` |
| C-10 | Plantillas de ruta renombradas por legibilidad (`{zone_id}`…) en lugar de las de la especificación (`{id}`, `{v}`, `{property}`) | Compilar el cliente de R4 contra el OpenAPI de R3 | Alias de `Path` (nombres claros en el código, `{id}` en OpenAPI; URL idéntica) | `test_routes_match_except_the_known_health_path_difference` |
| C-09 | Respuesta de login sin los campos que usa el cliente de R4 | Lectura de `session.ts` | `expires_in` y `role` (aditivos) | `test_login_response_is_compatible_with_the_r4_session_client` |
| S-01 (R3 sin defensa) | R3 no comprobaba al arrancar que RLS no pudiera evadirse; un script ajeno (el 92 de R1) puede romperlo | Demostración con fuga real | `api.db.invariants`: el servicio **se niega a arrancar** si el rol es superusuario/BYPASSRLS, falta RLS en una tabla protegida o una vista no usa `security_invoker` | `test_service_refuses_to_start_if_a_view_can_bypass_rls`, `test_r1_script_92_is_detected_by_the_startup_guard` |
| — | `GET /reports/{id}/pdf` anunciaba también `application/json` | Comparar con R4 | Solo `application/pdf` | prueba de contrato |
| C-14 (parte R3) | El renderizador perdía en silencio las hojas de estilo enlazadas por la plantilla de R4 | PDF real con y sin CSS | `inline_local_stylesheets` (sin ampliar la política de red «solo `data:`») | `test_r4_template_pdf_keeps_its_stylesheet_and_a4_page_size` (Docker) |

**Rectificación del informe anterior.** El informe final entregado antes de esta auditoría presentaba el esquema CSV como pendiente de R1. Era incorrecto: el README lo define (§9). `docs/integration/R1_DATA_CONTRACT.md` e `INTEGRATION_STATUS.md` se corrigieron.

## 2. Requisitos R3-F01…F22

Clasificación del encargo. «Prueba» = comando/archivo en `informe_validacion.md`.

| ID | Requisito | Clasificación | Detalle |
|---|---|---|---|
| R3-F01 | API `/v1` con OpenAPI | Implementado correctamente | 34 operaciones; Schemathesis; plantillas de ruta como la especificación |
| R3-F02 | JWT + Argon2id | Implementado correctamente | login/expiración/alg fijo/rol desde BD |
| R3-F03 | RBAC por pertenencia | Implementado correctamente | dueño, técnico asignado, ajeno |
| R3-F04 | RLS | Implementado correctamente | rol real sin BYPASSRLS; guardia de arranque nueva |
| R3-F05 | Consentimiento y retirada | Implementado parcialmente | Verificación y bloqueo por propósito sí; **alta/retirada por API sin contrato definido** (servicios y CLI) |
| R3-F06 | Borrado de parcela como trabajo | Implementado parcialmente | Dueño sí; ruta de admin bloqueada (política DP-13); tipos de trabajo extra pendientes de aprobación (ADR-007) |
| R3-F07 | Trabajos persistentes | Implementado correctamente | idempotencia, cancelación, recuperación |
| R3-F08 | Zonas | Implementado parcialmente | Consulta autorizada sí; `POST /zones` crea el trabajo pero la ingesta espera a R1 (`IngestPort`) |
| R3-F09 | Parcelas sin geometría exacta | Implementado correctamente | rejilla ≥ 1 km |
| R3-F10 | CSV de suelo | Implementado parcialmente | Validación conforme al README §9; **guardar exige reglas de evidencia de R2** (503 si faltan) |
| R3-F11 | Estado de propiedades de suelo | Implementado correctamente | DTO idéntico (9/9 campos) al de R4. Nota: el script 92 de R1 cambia la vista (C-08, S-01) |
| R3-F12 | Adaptador Parquet | **Incompatible** con el artefacto real | Valida ruta/esquema/hash, pero el Parquet de R1 no trae `cell_id` (C-02); decisión pendiente |
| R3-F13 | Adaptador `milpa_core` | Implementado parcialmente | Interfaz y comprobación de contrato; `milpa_core` no existe |
| R3-F14…F18 | Corridas, resumen, heatmap, decenas, ranking, escenarios, Soil VoI | Implementado parcialmente | Ruta, autorización, trabajos y errores; carga útil opaca `pending_r2`; sin R2 → 503 |
| R3-F19 | Procedencia | Implementado correctamente | Forma `ProvenanceInfo`; permisos por RLS |
| R3-F20 | PDF | Implementado parcialmente | Jinja2 + WeasyPrint, hash, privacidad; plantilla provisional **y** capacidad de usar la de R4 (verificada con contexto sintético); falta `report_model` de R2 |
| R3-F21 | Modo demo | No implementado | Depende de `data/demo/` (R1) |
| R3-F22 | Reproducción por hashes | Implementado parcialmente | Verificador y `make reproduce` (exit 2/3 sin datos); equivalencia de `data_hash` con R1 no verificada (C-16) |

## 3. Principios del backend (CLAUDE.md)

| Principio | Resultado | Evidencia |
|---|---|---|
| No duplicar ciencia de `milpa_core` | Cumple | `tests/contract/test_boundaries.py::test_no_scientific_algorithms_in_the_api` y `test_milpa_core_is_only_touched_by_its_adapter` |
| No importar `milpa_etl` | Cumple | ídem |
| No inventar contratos | **Corregido** (C-15, ProvenanceInfo, rutas) | arriba |
| Respetar RLS / `SET LOCAL app.user_id` | Cumple; ahora con guardia | `test_rls.py` |
| No registrar tokens/contraseñas/coordenadas/cuerpos | Cumple | `test_privacy_leaks.py` |
| Hashes SHA-256 de procedencia preservados | Cumple (transporta); equivalencia con R1 sin verificar | C-16 |
| Reproducibilidad del informe | Cumple en Docker (mismo SHA-256 entre contenedores) | `docs/REPORTS.md` |

## 4. Riesgos abiertos de R3

1. Los contratos `provisional_r3` (rutas de análisis, DTO de zonas/runs, listados) pueden cambiar cuando R2/R4 los confirmen; cada cambio requiere ADR.
2. Dos tipos de trabajo adicionales (`parcel_delete`, `consent_purge`) y la propiedad de las migraciones de R1 (ADR-003, 007, 009, 010, 015, 016) siguen **pendientes de aprobación**.
3. La suite completa en el host Windows no ejecuta las pruebas de PDF (sin Pango): se ejecutan en Docker (`make test-docker`).
