# Product

<!-- impeccable:product-schema 1 -->

> Escrito a partir del documento «MILPA RESILIENTE 3.3 — MVP» y del brief de rediseño. No hubo entrevista: lo marcado como (inferido) no fue confirmado por una persona.

## Platform

web

## Users

Técnicos agrícolas y cooperativas, agricultores y organizaciones que comparan estrategias agrícolas frente a 25 años de clima y escenarios sintéticos; financiadores que revisan qué evidencia respalda cada cifra. Usan la herramienta para decidir con información y ver qué falta verificar en campo. (inferido de §2 del documento)

## Product Purpose

Sistema explicable que compara estrategias (asociaciones, rotaciones, fechas, variedades) por su consistencia ante condiciones desfavorables y muestra los conflictos entre objetivos. No es un pronóstico, ni un simulador de rendimiento, ni una recomendación automática.

## Positioning

Cada cifra viaja con su procedencia y nivel de evidencia (A/B/C); lo que falta se declara en lugar de rellenarse. Proyecto del NASA Space Apps Challenge.

## Capabilities and Constraints

Cuatro pantallas existentes (Mi zona, Cómo cambió el calendario, Laboratorio de rotaciones, Informe de decisión). El rediseño solo cambia presentación: sin funciones, módulos, datos ni rutas nuevas, y sin tocar API, contratos ni lógica científica. Los datos mostrados hoy son un fixture sintético rotulado, no datos reales.

## Brand Commitments

Nombre MILPA RESILIENTE. Referencia institucional y científica: INSIVUMEH, solo como inspiración (sin copiar estructura, logotipo ni identidad). Paleta agrícola: verde, tierra, maíz y azul atmosférico. Contraste WCAG 2.2 AA como mínimo.

## Evidence on Hand

Ninguna cifra real del piloto. El fixture sintético (`apps/web/src/api/mock-fixture.ts`) es solo para probar la interfaz.

## Product Principles

1. Ningún número sin procedencia ni nivel de evidencia.
2. El motor decide etiquetas y estados; la interfaz solo los presenta.
3. Un dato desconocido nunca es cero y nunca se inventa.
4. Los estados y los riesgos no dependen solo del color.
5. La interfaz aclara los límites del producto: no es pronóstico ni recomendación.

## Accessibility & Inclusion

WCAG 2.2 AA como mínimo; uso con teclado; movimiento reducido respetado; objetivos táctiles de al menos 44 px en controles principales.
