# ADR-003: Esquemas PostgreSQL y propiedad de migraciones

- **Fecha:** 2026-11-14 · **Estado:** **propuesto — requiere aprobación de R1 y R3** (toca un contrato compartido)

## Contexto y problema
El orden de migración es `auth → prov → ref → geo → farm → private → soil → econ → engine → report`. El reparto de roles asigna `prov/ref/geo/soil/econ` a R1 (DE-01), pero las tablas de R3 (`farm`, `engine`, `report`) dependen de ellas por FK y existe un único Alembic. Además `ref.strategy.region_id → geo.region` es una FK hacia adelante respecto del orden indicado (C3).

## Restricciones
Spec R3 §8.4: no crear dos cadenas Alembic ni duplicar migraciones; no declarar definitivo un esquema no aprobado.

## Alternativas
1. Dos cadenas Alembic (R1 y R3) — prohibido por la especificación.
2. R3 crea solo `auth/farm/private/engine/report` sin FKs a R1 — rompe integridad referencial.
3. **Una cadena en `apps/api/migrations`; las revisiones de R1 se escriben desde el DDL [Propuesto] del README §13 y se rotulan `OWNER: R1 / provisional` (elegida).**

## Decisión
Cadena única 0001…0013 (`base, auth, prov, ref, geo, farm, private, soil, econ, engine, report, rls, grants`). R1 asume el contenido de sus revisiones por PR sin alterar el orden ni los `revision id`. La FK de `ref.strategy` hacia `geo.region` se añade en la revisión `0005_geo` (C3). Extensiones de R3 marcadas `R3-EXT` en el SQL (columnas de bloqueo de login, `auth.audit_log`, `created_at/created_by` de parcela, índices únicos).

## Consecuencias
(+) Un clon limpio migra y las FK se verifican. (−) Hasta la aprobación, el DDL de R1 es provisional y puede cambiar; las pruebas de paridad (enums) y la vista `soil.property_status` (con `security_invoker`) lo ejercitan.

## Riesgos
Divergencia si R1 altera su DDL fuera de la cadena. Mitigación: PR obligatorio con revisión de R3 sobre `migrations/`.

## Módulos afectados
`apps/api/migrations/**`, `docs/DATABASE.md`. **Aprobadores:** R1, R3.
