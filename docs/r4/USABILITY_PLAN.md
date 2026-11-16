# UX-09 — Plan de pruebas de usabilidad

Estado: metodología preparada. No se han reclutado ni entrevistado participantes y no hay resultados observados. La ejecución con personas reales depende del permiso y la disponibilidad del socio local (DP-15).

## Objetivos

1. Comprobar si técnicos y agricultores entienden qué compara el producto y qué preguntas no responde.
2. Observar si pueden encontrar fuentes, cobertura, faltantes y estado individual del suelo.
3. Comprobar si distinguen exposición climática (Modo A) de balance hídrico radicular (Modo B).
4. Comprobar si leen frecuencia, severidad, `n_valid`, evidencia A/B/C y procedencia sin confundirlos con rendimiento o certeza.
5. Evaluar comprensión de los cuatro estados del heatmap, escenarios sintéticos, valores hipotéticos y estabilidad del ranking.
6. Comprobar si el informe permite identificar decisiones pendientes y verificaciones de campo.

## Participantes y condiciones

- Perfiles: técnicos agrícolas/cooperativas y agricultores que el socio local autorice.
- No se fija un número de participantes antes de acordarlo con el socio; no se reportará una muestra inexistente.
- No recoger coordenadas exactas, nombres ni información de parcela real en notas de observación.
- Usar solo datos demo congelados o fixtures sintéticos rotulados; separar claramente los dos tipos.
- Solicitar consentimiento de participación según el proceso local. La sesión no es una validación agronómica ni una recomendación de manejo.

## Preparación de sesión

1. Confirmar con el socio local perfil, idioma, consentimiento, lugar, dispositivo y disponibilidad.
2. Congelar versión de la app, `run_id`, `data_hash`, catálogos y fixtures usados.
3. Preparar estado de solo lectura y cuentas de prueba; no cargar datos reales de participantes.
4. Registrar versión del guion, observador, incidencias técnicas y contexto de dispositivo, sin identificadores personales.
5. Si el entorno integrado aún no existe, limitarse a revisión de prototipo y no describirla como prueba del producto funcional.

## Tareas para participantes

| Tarea | Pantalla | Observación |
|---|---|---|
| 1. Encuentre qué zona y datos se están usando; explique qué falta saber | Mi zona | Fuentes, instituciones, cobertura, resolución y estados desconocidos |
| 2. Localice el estado del pH y diga qué significa la opción de Soil VoI | Mi zona | Diferencia entre medido, estimado, hipotético, no disponible e información insuficiente |
| 3. Encuentre una etapa crítica y explique qué representa una decena marcada | Cómo cambió el calendario | Indicador del motor, Pef/ETc, umbral provisional, `n_valid` y modo |
| 4. Compare dos estrategias y cambie el peso de alimentación frente a ingreso | Laboratorio de rotaciones | Cambios del orden, peso efectivo, soporte común y conflicto entre criterios |
| 5. Explique qué indica la estabilidad y qué no indica | Laboratorio de rotaciones | Comprensión de sensibilidad a pesos; no probabilidad de ser la mejor |
| 6. Seleccione un escenario sintético y describa sus supuestos | Laboratorio de rotaciones | Identificación persistente del escenario y diferencia con BASE; si no está calculado, aviso/solicitud de trabajo |
| 7. Revise el informe e indique qué falta verificar en campo | Informe de decisión | Limitaciones, procedencia, datos faltantes, resumen inglés, hashes y privacidad |

El facilitador lee la instrucción sin explicar las respuestas. Se permite que la persona piense en voz alta; el facilitador no guía salvo que se deba detener por accesibilidad o error técnico.

## Registro de observación

Por tarea, anotar de forma no identificable:

- Inicio, finalización, abandono o bloqueo; ayuda solicitada.
- Primer elemento que la persona consulta y recorrido de navegación.
- Interpretación verbal de cifra, unidad, procedencia y evidencia.
- Confusiones observadas: exposición vs agua del suelo; escenario vs pronóstico; hipotético vs medido; sensibilidad vs probabilidad; cohorte vs ciclo/fecha.
- Problemas de teclado, foco, contraste, lector de pantalla o tamaño adaptable.
- Cita textual breve solo si no incluye dato identificable; de lo contrario, paráfrasis.
- Severidad: bloquea tarea / induce interpretación incorrecta / retrasa tarea / mejora sugerida.

## Evaluación y síntesis

No se fijan umbrales de éxito cuantitativos antes de acordarlos con el equipo/socio. Para cada problema observado se reportará evidencia, tarea, perfil general, impacto, frecuencia dentro de la muestra real, propuesta y responsable. No extrapolar porcentajes a la población ni inventar resultados. Separar hallazgos observados, interpretación del equipo y cambios propuestos.

## Plantilla de informe de resultados (vacía hasta ejecutar)

- Fecha y versión:
- Contexto y participantes autorizados (agregado, sin datos identificables):
- Dispositivo/idioma:
- Datos y `run_id` usados:
- Tareas ejecutadas / no ejecutadas y motivo:
- Observaciones por tarea:
- Problemas priorizados y evidencia:
- Comprensión de indicadores/procedencia:
- Hallazgos de accesibilidad:
- Cambios propuestos:
- Limitaciones de la sesión:
- Estado: pendiente de ejecución.
