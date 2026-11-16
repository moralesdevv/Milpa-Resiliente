# ADR-002: Stack FastAPI / SQLAlchemy 2 / Alembic y driver PostgreSQL

- **Fecha:** 2026-11-14 · **Estado:** aceptado (stack); **propuesto** (driver `psycopg` 3 y `pydantic-settings`)

## Contexto y problema
La especificación fija FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, GeoAlchemy2 y uv, pero deja abierta la selección del driver PostgreSQL (§5.3, DP "Driver PostgreSQL") y no menciona cómo validar la configuración.

## Alternativas
- Driver: `psycopg2-binary` (maduro, sin soporte async nativo), `asyncpg` (async, obliga a SQLAlchemy async y complica `SET LOCAL`/pool por proceso), **`psycopg` 3 (elegido)**.
- Estilo: SQLAlchemy asíncrono vs **síncrono** (elegido): los endpoints son `def` y FastAPI los ejecuta en su pool de hilos; el worker usa procesos y sesiones síncronas independientes. Menos riesgo en el contexto RLS por transacción.
- Configuración: `os.environ` manual vs **`pydantic-settings`** (misma familia Pydantic v2; validación al arrancar).

## Decisión
`postgresql+psycopg://` (psycopg 3, binario), ORM síncrono 2.x, Alembic con **una sola cadena** (ADR-003), `pydantic-settings` para `Settings`. Versiones exactas en `uv.lock`.

## Consecuencias
(+) Compatible con GeoAlchemy2, `SET LOCAL` y procesos `spawn`. (−) Sin E/S asíncrona en la base; aceptable para el volumen del MVP. Si una medición real lo justifica, reabrir con ADR.

## Riesgos
Compatibilidad SQLAlchemy 2.1/GeoAlchemy2 0.21 (verificada con las pruebas de integración). **Aprobador:** líder R3.
