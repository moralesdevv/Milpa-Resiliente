# ADR-005: Autenticación JWT + Argon2id

- **Fecha:** 2026-11-14 · **Estado:** aceptado (mecanismo); **propuesto** (valores operativos y registro de usuarios)

## Contexto
Roles `tecnico`, `agricultor`, `admin`. JWT Bearer de vida corta, Argon2id, bloqueo progresivo, sin refresh tokens en el MVP.

## Decisión
- **Contraseñas:** `argon2-cffi` (`PasswordHasher(type=ID)`, parámetros por defecto RFC 9106), longitud 12–256. Verificación contra un hash ficticio cuando el usuario no existe (igualar tiempos).
- **JWT:** PyJWT, HS256 **fijo** (`algorithms=["HS256"]`, nunca leído del token), claims obligatorios `sub, role, exp, iat, iss, aud, jti`. TTL configurable (`JWT_TTL_MINUTES`, por defecto 15, máx. 120). Rotación: `JWT_SECRET_PREVIOUS` solo verifica.
- **Rol de autoridad:** el rol efectivo se lee de la base de datos, no del token.
- **Bloqueo progresivo:** umbral 5 fallos; espera `60 s · 2^(n−umbral)` con tope 900 s (configurables). Mismo mensaje y código 401 para usuario inexistente, contraseña errónea, cuenta bloqueada o deshabilitada.
- **Límite de tasa:** ventana deslizante en proceso por IP y por usuario (sin dependencias nuevas).
- **Sin registro público:** el contrato de registro no está definido; las cuentas se crean con la CLI (`python -m api.cli create-user`) usando el rol propietario.

## Alternativas
RS256/EdDSA (útil con varios verificadores; innecesario con un solo servicio), sesiones con cookie (CSRF), proveedor externo (infraestructura nueva).

## Consecuencias y riesgos
(+) Superficie mínima. (−) HS256 exige proteger `JWT_SECRET`; los tokens no son revocables antes de expirar (TTL corto lo acota); el limitador por proceso no escala a varias réplicas. Valores del bloqueo/TTL: pendientes de decisión de seguridad.

**Aprobadores:** líder R3 / responsable de seguridad.
