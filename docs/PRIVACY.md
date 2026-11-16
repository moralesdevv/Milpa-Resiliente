# Privacidad (R3)

Principio: **no tener lo que no se necesita** (README §22). El clima disponible tiene 10–50 km de resolución: una geometría exacta de parcela no mejora ningún resultado.

## 1. Niveles de ubicación
| Nivel | Dónde | Quién | MVP |
|---|---|---|---|
| Geometría exacta | `private.parcel_geometry` (RLS, solo dueño; consentimiento `exact_geometry`) | dueño | **Desactivada**: `ENABLE_EXACT_GEOMETRY=true` impide arrancar; ningún endpoint la acepta |
| Ubicación generalizada | `farm.parcel.display_geom` = **centro de celda UTM de ≥ 1000 m** (`ST_SnapToGrid`), `display_grid_m ≥ 1000` | dueño y técnico asignado | Sí; la API la devuelve redondeada a 3 decimales |
| Coordenadas de análisis | `geo.zone` | autenticados | Sí |
| Informe público | nombre de la zona; sin persona, código de parcela, correo ni coordenadas | quien lo reciba | Sí (verificado antes de generar) |

El punto elegido en el mapa solo viaja como parámetro de una consulta que lo generaliza; **no se persiste ni se registra**, y los mensajes de error no repiten coordenadas (`test_database_stores_no_exact_coordinates…`, `test_privacy_leaks.py`).

## 2. Consentimiento
Propósitos: `analysis`, `report_sharing`, `exact_geometry`. Se guardan versión del texto, concesión y retirada; uno vigente por sujeto/propósito. Sin consentimiento vigente: no se crean parcelas, perfiles, cargas de suelo ni corridas/informes sobre la parcela (`403 CONSENT_REQUIRED`) y el técnico asignado pierde visibilidad (RLS). La retirada **bloquea nuevos usos** y encola `consent_purge`:
- `analysis`: borra corridas, resultados y PDFs derivados de las parcelas del sujeto (los datos de suelo permanecen hasta borrar la parcela, según la tabla de retención).
- `report_sharing`: borra los informes `public` (y sus PDFs).
- `exact_geometry`: borra la geometría privada.
No hay endpoints HTTP para conceder/retirar (contrato pendiente, ADR-010): servicio `ConsentService` + CLI.

## 3. Borrado de parcela (`DELETE /v1/parcels/{id}`, trabajo `parcel_delete`)
Elimina parcela, mediciones, muestras, declaraciones, historial, perfil, geometría privada, corridas y sus resultados (`results/<run_id>`), informes y PDFs, y la procedencia asociada. Reanudable (checkpoint) e idempotente. Auditoría: solo identificadores y fecha. Solo el dueño por ahora; la vía **admin** requiere una política de acceso excepcional registrada (no aprobada).

## 4. Minimización y retención
| Dato | Retención implementada | Pendiente |
|---|---|---|
| Cuenta (correo, hash Argon2id) | mientras exista la cuenta | política de baja |
| Agricultor (seudónimo, comunidad), suelo, historial | hasta borrar la parcela o retirar consentimiento (según tabla) | — |
| Resultados por parcela y PDF | hasta borrado o retirada de `analysis` | — |
| Registros técnicos | no se guardan datos personales; sin rotación definida | **plazo (DP-13)** |
| Copias de seguridad | — | **política (DP-13)** |
No usar datos personales reales hasta aprobar retención de logs y backups.

## 5. Lo que nunca debe aparecer (con pruebas)
Coordenadas exactas, correos, nombres, tokens, hashes de contraseña o contenido de CSV en: registros, errores, informes `public`, paquete de demostración, OpenAPI. Pruebas: `tests/privacy/`. El escaneo de `data/demo/` se activará cuando R1 lo entregue (hoy se omite con motivo).

## 6. Decisiones pendientes (DP-13)
Tamaño definitivo de rejilla (≥1 km), texto y versión del consentimiento, retención de logs/artefactos/backups, política de acceso excepcional del administrador, revisión legal.
