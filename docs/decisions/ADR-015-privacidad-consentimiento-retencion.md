# ADR-015: Minimización geográfica, consentimiento, retención y borrado

- **Fecha:** 2026-11-14 · **Estado:** **propuesto** — decisiones DP-13 pendientes de revisión legal/operativa

## Decisión
- **No tener lo que no se necesita:** `ENABLE_EXACT_GEOMETRY=false`; con `true` la aplicación **no arranca** (nivel B no implementado). El contrato de `POST /parcels` no admite geometría exacta (`extra=forbid`); el punto elegido en el mapa se generaliza en el servidor (ADR-004) y no se persiste ni se registra.
- **Consentimiento por propósito** (`analysis, report_sharing, exact_geometry`) con versión de texto, concesión y retirada; uno vigente por sujeto/propósito. Retirar: bloquea **nuevos** usos (`CONSENT_REQUIRED`; el técnico pierde visibilidad por RLS) y encola `consent_purge` (analysis → resultados/PDF por parcela; report_sharing → informes públicos; exact_geometry → geometría privada).
- **Borrado de parcela** como trabajo `parcel_delete` (dueño): filas dependientes, procedencia, corridas/resultados, informes, PDFs y árboles `results/<run_id>`; checkpoint para completar la limpieza de archivos tras una caída. Auditoría (`auth.audit_log`) con **solo identificadores técnicos y fecha**.
- **Admin:** sin acceso automático a contenido privado. El borrado por admin y el acceso excepcional registrado **quedan bloqueados** hasta aprobar la política (C8).
- Registros JSON con redacción (correo, coordenadas >3 decimales, JWT/Bearer, hashes, `postgresql://usuario:clave@`), sin cuerpos de petición ni SQL con parámetros (`hide_parameters`).
- Pendientes: tamaño de rejilla definitivo (≥1 km), retención de registros técnicos, retención en copias de seguridad, texto de consentimiento, política de acceso excepcional (DP-13).

## Riesgos
Sin política de backups no debe usarse información personal real. **Aprobadores:** equipo + revisión legal.
