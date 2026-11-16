> **SUPERADO (2026-11-16):** la validación de siembra se amplió (cultivos, ciclos, Kc, fenología, inicio de lluvias y estación Camotán). Ver `docs/VALIDACION_AGRONOMICA_JOCOTAN.md` y ADR-023. Este documento describe la primera versión.

# Revisión de fecha de siembra para Jocotán

## Configuración

`regions/reglas_agronomicas_jocotan.json` contiene la regla de maíz de primera:

- Ventana configurada: 1 de mayo a 30 de junio, inclusive.
- Variedades admitidas: ICTA B-7, B-9 y B-15.
- Lluvia acumulada mínima: 20 mm durante el día de siembra y los 14 días siguientes.
- Racha seca: alerta cuando hay más de 10 días consecutivos con lluvia diaria menor de 1 mm en ese periodo.
- Temperatura: promedio de TMAX/TMIN de POWER para el día de siembra, comparado con 22–32 °C.

Los umbrales se recibieron como reglas del piloto y se marcan `sandbox`; necesitan validación
agronómica local antes de usarlos como recomendación oficial. MAGA/ZARC documentan ventanas y
probabilidades a escala municipal, mientras ICTA documenta la tolerancia a sequía de ICTA B-7.

## Endpoint y datos

`POST /v1/parcels/{id}/planting-validation`

```json
{
  "fecha_siembra": "2025-05-01",
  "variedad": "ICTA B-7"
}
```

La respuesta incluye `es_valido`, `alertas`, `recomendacion`, métricas, fuentes de lluvia y cobertura.
La precipitación es la serie diaria curada de R1 (IMERG con respaldo POWER); temperatura máxima y
mínima proceden de POWER. Se consulta la serie compartida de la zona `camotan_jocotan`, porque R3
no conserva coordenadas exactas de parcela ni genera clima parcelario.

La cobertura disponible termina el 31 de diciembre de 2025. Una fecha futura o un periodo con días
faltantes devuelve datos insuficientes; la serie histórica no se presenta como pronóstico. La
validación tampoco reemplaza observaciones de lluvia, análisis de suelo o asistencia técnica.

La interfaz Mi zona ofrece el formulario cuando hay una parcela identificada en Jocotán/Camotán.
