# UX-10 — Guion de demostración

Estado: el recorrido ya se puede **ensayar con el simulado de R4** (`npm run web:dev:mock`, run `run-synthetic-0001`, parcela `parcel-synthetic-001`), que sirve un fixture **sintético rotulado**: sirve para ver cómo funcionan las pantallas, no para presentar resultados. La demostración real sigue bloqueada: faltan `data/demo/`, `EXPECTED.json`, el mock/API de R3 y las respuestas de R1/R2. No se mezclan fixtures con datos del piloto y la audiencia debe saber que los valores son de prueba. Notas de las pantallas en la versión actual: el mapa muestra celdas y una ubicación generalizada (no hay geometría exacta); las mutaciones piden iniciar sesión; las combinaciones de escenario no calculadas se lanzan como trabajo.

## Precondiciones

- Entorno de solo lectura; sin acceso en vivo a APIs NASA.
- Confirmar que las respuestas y cifras proceden del `run_id`/`data_hash` congelado y muestran Indicator/procedencia.
- Mostrar únicamente escenarios y estrategias calculados; si un escenario no fue precalculado, explicar que requiere trabajo sin simular el resultado.
- Mantener visibles modo, evidencia, provisionalidad y etiqueta «escenario sintético» donde corresponda.
- No utilizar nombres, códigos de parcela, geometría exacta ni ubicaciones más precisas que la zona.

## Recorrido (aprox. 8–10 minutos; duración orientativa, no requisito de producto)

| Paso | Pantalla y acción | Narrativa y criterio de fidelidad |
|---|---|---|
| 1. Presentar la zona | Mi zona: abrir zona demo, región, elevación/pendiente y fuentes | Explicar la unidad climática y sus fuentes. El mapa/celdas espera DTOs seguros de R1/R3; no dibujar parcelas ni coordenadas con el contrato actual. |
| 2. Revisar fuentes/calidad | Mi zona: abrir la sección de calidad y procedencia | Identificar institución, versión, periodo y resolución cuando estén en DTO. Con el esquema actual la cobertura/calidad se muestra pendiente; no completar esos datos de memoria. |
| 3. Ver historial climático | Cómo cambió el calendario: abrir la consulta de historial | El DTO de historial no está definido en §15; hoy se muestra el estado pendiente. Cuando R1/R2/R3 lo entreguen, describir solo el resumen recibido y sus Indicators. |
| 4. Explorar indicador crítico | Abrir DekadChart cuando exista una corrida congelada | Mostrar Pef y ETc, etapa crítica, decena sobre umbral y sus Indicators. Distinguir exposición Modo A de balance radicular Modo B; si no hay payload o cita, conservar el estado insuficiente/provisional. |
| 5. Comparar estrategias | Laboratorio de rotaciones: revisar resultados si el mock oficial los entrega | Explicar frecuencia, severidad, P90, CVaR90, peor año, cobertura y cohortes desde los Indicators. Sin datos congelados, mostrar la condición pendiente. |
| 6. Cambiar prioridades | Mover pesos de criterios manteniendo suma 1, con ranking disponible | Mostrar criterios no evaluables/provisionales, soporte común, `weight_coverage`, decision log y razones del orden solo si el contrato R2/R3 entrega esos campos. No atribuir puntuaciones a filas sin identidad de estrategia. |
| 7. Explorar escenario | Elegir solo un escenario precalculado y su adaptación | Leer parámetros, humedad, método y lectura; identificar «escenario sintético» en tarjetas/gráficos. Comparar contra BASE. Decir que es perturbación histórica y no pronóstico. |
| 8. Consultar estabilidad | Abrir StabilityMeter cuando haya respuesta de ranking | Decir que mide sensibilidad a pesos, no probabilidad de ser la mejor. Señalar el estado del enum y conflictos recibidos del motor. |
| 9. Generar/revisar informe | Informe de decisión: vista de plantilla y PDF cuando R3 esté conectado | Mostrar la estructura A4 bilingüe y privacidad; después, con PDF real, revisar anexo, advertencias, pendientes, `run_id` y hashes. La vista actual no representa un informe ya generado. Leer «No es una recomendación automática». |

## Cierre

Recordar qué evidencia está disponible, qué información falta y qué puntos deben contrastarse con personas expertas y en campo. Las decisiones permanecen en manos de agricultores y técnicos; el producto organiza evidencia y sensibilidad dentro de los límites declarados.

## Registro de ensayo de demostración (sin rellenar antes de ejecutar)

- Fecha/versión:
- `run_id`, `data_hash`, `catalog_hash`:
- Perfil de entorno y modo de privacidad:
- Pasos completados:
- Errores o escenarios no calculados:
- Problemas de navegación/accesibilidad:
- Acciones correctivas:
- Estado: pendiente de demostración integrada.
