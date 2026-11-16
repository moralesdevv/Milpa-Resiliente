# ADR-019 — Sesión pública de demostración y endpoint `POST /v1/auth/demo-session`

**Estado:** propuesto (requiere aprobación humana) · **Fecha:** 2026-11-16

## Contexto
El botón LAUNCH DEMO debe permitir explorar el sistema sin iniciar sesión. La API exige JWT en todas las rutas salvo `login` y `healthz` (spec R3 §10.2) y protege los datos con RLS.

## Decisión
- Nuevo endpoint público `POST /v1/auth/demo-session`, **desactivado por defecto** (`DEMO_PUBLIC_ACCESS=false` ⇒ 404).
- Emite un JWT real con claim `demo=true` para una cuenta dedicada (`demo@milpa.local`, rol `tecnico`) creada con `python -m api.cli create-demo-user`: contraseña aleatoria descartada (nadie puede iniciar sesión con ella), sin parcelas ni agricultores asociados (RLS le oculta todo dato privado).
- Alcance limitado en `api/security/demo.py`, aplicado en `get_current_user`: solo lectura de zonas, corridas, catálogo, informes, trabajos y procedencia; escritura solo para crear corridas de zona, escenarios, rankings e informes. Todo lo demás (parcelas, suelo, borrados, administración) ⇒ 403.
- Vida del token: `DEMO_TTL_MINUTES` (120 por defecto, máx. 720). Se mantienen límite de tasa por IP y por usuario.

## Consecuencias
- Un endpoint más (35 operaciones; hoy 40, ver ADR-023); se actualizan los contratos de prueba (`tests/contract`).
- Riesgo residual: cualquiera puede crear corridas en la zona piloto (limitado por tasa). Mitigaciones pendientes: cuota por sesión y limpieza periódica de corridas demo.
- No se desactiva ninguna medida de seguridad existente.
