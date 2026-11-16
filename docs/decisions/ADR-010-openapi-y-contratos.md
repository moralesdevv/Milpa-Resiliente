# ADR-010: OpenAPI, versionado de contratos, códigos de error y mock

- **Fecha:** 2026-11-14 · **Estado:** **propuesto** (extensiones de contrato: C7)

## Contexto
FastAPI genera OpenAPI; la especificación fija rutas, formato de error (RFC 7807 ampliado) y códigos de dominio, pero **no** define varios payloads (`POST /zones`, `/parcels`, `/zones/{id}/runs`, `/reports`, CSV de suelo, registro de usuarios, consentimiento).

## Decisión
- Prefijo `/v1`; `docs/openapi/openapi.json` versionado y verificado por prueba (cualquier cambio de contrato es explícito en el PR; CI falla si difiere del generado).
- Cada esquema lleva `x-contract-status`: `confirmed_by_spec` · `provisional_r3` (propuesto por R3, no oficial) · `pending_r2` (DTO de R2 aún inexistente; carga opaca). Se prueba que ningún DTO de R2 se presente como definitivo.
- Errores: `ProblemDetail` (`type,title,status,code,detail,request_id,errors,hint`); el 422 de FastAPI se reemplaza por `ProblemDetail` en OpenAPI. Los mensajes de validación **no repiten el valor recibido**.
- Códigos de la spec + **extensiones R3** (pendientes de aprobación): `DEPENDENCY_NOT_INTEGRATED, DATASET_UNAVAILABLE, DATASET_INCOMPATIBLE, INTEGRITY_CHECK_FAILED, IDEMPOTENCY_CONFLICT, PAYLOAD_TOO_LARGE, UNSUPPORTED_MEDIA_TYPE, CONSENT_REQUIRED, READ_ONLY_MODE, INVALID_CURSOR, SERVICE_UNAVAILABLE, INTERNAL_ERROR`.
- Sin endpoints de registro ni de consentimiento hasta que se defina el contrato (servicios + CLI).
- **Mock:** servidor Python propio (`api.mock.app`, `make mock`) en lugar de Prism (añadiría Node/infraestructura). Solo sirve ejemplos documentados, etiquetados `X-Milpa-Mock: fixture`; los endpoints con DTO de R2 responden 501.
- Tipos TypeScript: `make types` usa `openapi-typescript` (herramienta de R4) y se omite con mensaje claro si falta Node.

## Consecuencias / riesgos
(+) Contrato explícito y auditable. (−) R4 debe tratar `provisional_r3` como inestable. **Aprobadores:** R2, R3, R4.
