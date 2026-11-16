# Sistema visual de MILPA RESILIENTE (frontend R4)

Registro durable del rediseño de presentación de `apps/web`. Solo cambia la apariencia y la experiencia de uso: no se añadieron pantallas, módulos, datos, capas ni funciones, y no se tocó API, contratos, lógica científica ni textos i18n.

Fuente de verdad: los tokens de `apps/web/src/styles.css` (sección 1) y `apps/web/src/components/charts/chartTheme.ts` (ECharts dibuja en canvas y no lee variables CSS; sus colores se mantienen a mano iguales a los tokens).

## Dirección

Plataforma científica de inteligencia agroclimática. La referencia institucional (INSIVUMEH) se tomó solo como criterio de seriedad: franja institucional, jerarquía clara de datos, módulo siempre identificado. No se copió estructura, logotipo ni elementos propios; la identidad es propia: verde de cultivo profundo, filete de maíz, tierra cálida y azul atmosférico para lo climático.

- **Barra superior**: verde profundo con filete de maíz inferior; la sección activa lleva subrayado de maíz.
- **Cabecera de módulo**: banda verde suave con curvas de nivel (textura del territorio) que identifica la pantalla; la etiqueta «MILPA RESILIENTE · MVP1» pasa a ser una marca discreta en la esquina.
- **Una sola elevación**: superficies blancas con borde fino; sin sombras salvo ventanas emergentes (inicio de sesión, tooltip del mapa).
- **Cifra primero**: en cada indicador el valor (Archivo, 700) manda sobre la etiqueta; la procedencia y la evidencia siguen visibles.

## Paleta

| Rol | Token | Valor |
|---|---|---|
| Primario (acciones, marca) | `--green-700` / `--forest-900` | `#1b6444` / `#0f3326` |
| Acento de marca (nunca significa riesgo) | `--maize-400` | `#f0b92f` |
| Tierra | `--earth-700/800/100` | `#6d4a2a` / `#4f3419` / `#efe4d3` |
| Clima y datos científicos | `--sky-700/800/100` | `#1f5f91` / `#174a70` / `#e1edf6` |
| Fondo / superficie | `--paper` / `--surface` / `--sand-50` | `#f6f4ec` / `#fff` / `#faf8f1` |
| Texto principal / secundario / terciario | `--ink` / `--ink-2` / `--ink-3` | `#1b2a23` / `#46554d` / `#55645c` |
| Borde decorativo / de control | `--line` / `--control-border` | `#d9d6c6` / `#76857a` |
| Éxito | `--ok-700` | `#1b6444` |
| Advertencia / provisional | `--warn-800` sobre `--warn-100` | `#5c3d00` / `#fcefc9` |
| Error / riesgo | `--risk-700/800/100` | `#9b2f27` / `#6f1f19` / `#f8e2de` |
| Informativo / escenario sintético | `--info-800` sobre `--info-100` | `#174a70` / `#e1edf6` |

Reglas: el maíz decora (filete, subrayado, foco sobre verde oscuro), nunca marca riesgo; el rojo arcilla es solo riesgo/error; el azul identifica clima y escenarios sintéticos; las advertencias van siempre con icono y texto.

Series de gráficos: agua/precipitación `#1f5f91`, demanda/ET0 `#a56b00`, exposición `#9b2f27`; estrategias `#1b6444 · #1f5f91 · #a56b00 · #6d4a2a · #4d5d56`. Los gráficos conservan `aria.decal` (patrones), de modo que ninguna serie depende solo del color.

## Tipografía

- **Atkinson Hyperlegible Next** (400–700): lectura, formularios y cifras en tablas (`tabular-nums`). Diseñada para máxima legibilidad.
- **Archivo** (600–800): títulos y valores de indicadores.
- Ambas autoalojadas en `apps/web/public/fonts` (latin y latin-ext, WOFF2, licencia OFL); sin peticiones a terceros ni dependencias nuevas. Pila de respaldo: Segoe UI / system-ui.

## Espaciado, forma y movimiento

- Espaciado en pasos de 4 (`--s-1` … `--s-7`); radios `6px` (controles) y `8px` (superficies).
- Curva `cubic-bezier(0.23, 1, 0.32, 1)`; 140 ms en controles, 200 ms en despliegues. Nunca `transition: all`.
- Pulsación `scale(0.97)`; hover solo con `(hover: hover) and (pointer: fine)`; sin animación en acciones de teclado.
- Una única entrada discreta por pantalla (opacidad + 4 px) y la ventana de inicio de sesión. `prefers-reduced-motion` anula animaciones y transiciones.

## Accesibilidad

- Foco visible 3 px: azul `#1f5f91` sobre superficies claras, maíz sobre barra y pie oscuros.
- Objetivos táctiles ≥ 44 px (controles; `pointer: coarse` sube los compactos).
- Estados de celda del mapa de calor: color + patrón + marca + texto.
- Iconos de sección: SVG propios (`components/common/Icon.tsx`), un solo trazo (1,75 px); sustituyen glifos Unicode.

## Contraste (WCAG 2.2 AA)

Validado con la fórmula de luminancia relativa WCAG sobre 86 pares reales, aplanando transparencias y truncando sin redondear: **0 fallos**. Extremos relevantes: texto principal 13,6:1; secundario 7,15:1; enlaces 6,36:1; botón primario 7,11:1; navegación inactiva 10,03:1; borde de controles 3,52:1 (mínimo 3:1); peor caso de texto sobre patrón del mapa de calor 5,58:1; series de gráfico entre 4,46:1 y 7,88:1. Los botones deshabilitados están exentos por WCAG pero siguen siendo reconocibles.

## Decisiones conscientes

- Los **tooltips de ECharts siguen desactivados** (`tooltip.show: false`): activar valores flotantes mostraría cifras sin su procedencia, y la regla del producto es que toda cifra pasa por `Indicator`. Las tablas de datos asociadas cubren la lectura precisa.
- No se usó sidebar: la app tiene cuatro rutas y la barra superior se conserva (mismo orden de foco que antes).
- La cabecera deja de ser fija en teléfonos (≤ 680 px) para no ocupar la pantalla.

## Iteración 2 (referencias de dashboards agrícolas)

Solo presentación; mismas cuatro pantallas, rutas, datos y componentes funcionales.

- **Panel lateral** en escritorio (≥ 1181 px): verde profundo a altura completa con íconos y etiqueta de cada sección, idioma y sesión al pie; el módulo activo se marca con fondo y icono de maíz. Por debajo de ese ancho se conserva la barra superior con navegación deslizable (mismo orden de foco).
- **Cabecera de módulo editorial**: título grande sobre el lienzo, pregunta debajo y curvas de nivel como textura; ya no es una caja.
- **Indicador compacto** en tablas: cifra arriba; debajo `Ev. C · modelado · Prov.` y un botón «i» que abre la procedencia completa en un panel flotante (`position: fixed`, se cierra con Escape, clic fuera, desplazamiento o cambio de tamaño; Escape devuelve el foco). Nada se eliminó: la etiqueta y el motivo siguen en el árbol de accesibilidad.
- **Banda de escenario sintético** compacta y siempre visible junto a cada gráfico o tarjeta afectada.
- **Cifras clave** (elevación, pendiente, cobertura de pesos, margen) con numeral de 2 rem.
- **Mapa de calor** con celdas más bajas (25 años caben sin recorrer tres pantallas).
- **Radios**: 8 px en controles y 12 px en superficies.

### Contraste de la iteración 2 (WCAG 2.2 AA, calculado sin redondear hacia arriba)

27 pares comprobados, 0 fallos. Peores casos de texto: pregunta de pantalla 7,15:1, texto de navegación 8,89:1 (activo) y 10,87:1 (inactivo), bandera «Prov.» 8,63:1, insignia de evidencia C 9,09:1. Gráficos e íconos: icono inactivo del panel 7,15:1, icono activo de maíz 4,94:1, borde de controles 3,88:1, foco azul 6,14:1 y foco de maíz sobre el panel 7,67:1.

### Decisiones y límites

- No se añadió ninguna tipografía: la referencia usa titulares con serifa, pero el proyecto conserva Archivo y Atkinson (legibilidad de cifras, sin dependencias nuevas).
- Los mapas siguen sin teselas (no hay proveedor configurado): se dibujan solo las celdas y la ubicación generalizada, sobre una textura de curvas de nivel. No se añadió ninguna imagen satelital.
- No se copió ningún panel oscuro de la segunda referencia: habría exigido un tema oscuro completo.

## Iteración 3 — tierra, cultivo y observación satelital

Pedida como identidad propia de exploración científica, no de dashboard empresarial. Solo presentación; mismas pantallas, rutas, datos, componentes y lógica.

**Composición.** Cada módulo abre con un héroe a todo el ancho en verde bosque con curvas de nivel claras y filete de maíz. Las secciones son **bandas de color a todo el ancho** por tema (hoja para agricultura y estrategias, cielo para clima y fuentes, tierra para suelo y prioridades) y solo los datos —tablas, gráficos, tarjetas de riesgo— viven en paneles blancos. Ya no hay una caja alrededor de cada sección.

**Paleta viva** (tokens en `styles.css`, espejo en `chartTheme.ts`):

| Rol | Valor |
|---|---|
| Verde esmeralda (acción, marca) | `#067a52` |
| Verde bosque / bosque profundo (héroe, panel lateral) | `#073b2a` / `#04261b` |
| Verde hoja / verde vivo (fondos y gráficos) | `#d9f1e3` / `#35c26a` |
| Amarillo maíz (acento, filete, activo) | `#ffc933` |
| Azul atmosférico / cielo | `#0b659f` / `#dff1fb` · `#27a3e0` |
| Terracota / tierra | `#b8501f` / `#f5e3cc` |
| Crema (lienzo) | `#f9f2e0` |
| Riesgo (coral rojo, nunca de marca) | `#b8321f` |

El maíz y el esmeralda son marca; el coral rojo solo significa riesgo.

**Movimiento** (respeta `prefers-reduced-motion`): entrada escalonada de cada pantalla (opacidad + 10 px, 520 ms, retrasos de 0 a 285 ms); indicador del módulo activo que crece desde el borde del panel; botones con relieve, elevación al hover y hundimiento al pulsar; tarjetas y paneles que se elevan 2 px al hover; foco de formularios con anillo animado; gráficos con aparición progresiva (760 ms, `cubicOut`) y transición entre datos (420 ms), desactivados con movimiento reducido.

**Decisiones.**
- Los tooltips de los gráficos siguen apagados: mostrarían cifras sin procedencia. Las tablas asociadas dan la lectura exacta.
- La retícula cartográfica se dibuja solo sobre la superficie del mapa (donde representa coordenadas), no como decoración de fondo.
- Sin imágenes satelitales ni capas nuevas: el mapa sigue siendo celdas y ubicación generalizada sobre curvas de nivel.

**Validación.** 40 pares de contraste calculados antes de aplicar la paleta, 0 fallos; axe sin violaciones WCAG 2.1 A/AA en las cuatro pantallas con la paleta aplicada; sin desbordamiento horizontal a 375 y 768 px; detector de Impeccable: un aviso consultivo sobre la retícula del mapa (superficie cartográfica real).

## Iteración 4 — observatorio de la milpa (vigente)

Sustituye la composición de las iteraciones 2 y 3 (panel lateral, héroe plano). Presentación únicamente: mismas cuatro pantallas, rutas, datos, contratos y comportamiento.

**Concepto.** Cuatro pilares: observación de la Tierra, inteligencia agrícola, resiliencia climática y Guatemala (cultivos y territorio). El producto se lee como una exploración científica, no como un panel administrativo.

**Navegación: barra de misión.** Un solo borde superior noche con cuatro nodos conectados (territorio → clima → estrategias → informe): el módulo activo es un nodo de maíz con halo; los demás son círculos con borde. Entre 1024 y 1279 px solo la etiqueta del módulo activo es visible (las demás siguen disponibles para lectores de pantalla); bajo 1024 px la ruta pasa a una segunda fila desplazable; bajo 680 px la barra deja de ser fija.

**Héroe de módulo.** La Tierra vista desde órbita, dibujada en SVG (`components/common/HeroArt.tsx`): limbo con atmósfera, mosaico de parcelas, curvas de nivel, estrellas, órbita punteada y un satélite que recorre su órbita en 140 s. Es geometría decorativa, no representa datos. Cada módulo usa su color de acento (`--accent`): territorio verde vivo, clima azul cielo, estrategias maíz, informe terracota claro. El panel de filtros se solapa con el borde del héroe.

**Composición de atlas.** En escritorio, cada sección tiene su título en una columna lateral fija (a la izquierda) y la figura de datos a su derecha; las secciones anchas (riesgo, historial, comparación) ocupan todo el ancho. Las secciones son bandas de color a todo el ancho por tema; solo los datos van en paneles blancos, con una pestaña de acento en lugar de un filo grueso.

**Tipografía.** Bricolage Grotesque (títulos, expresiva y científica a la vez), Atkinson Hyperlegible Next (lectura), JetBrains Mono (cifras, identificadores y etiquetas de módulo: lecturas de instrumento). Las tres autoalojadas con licencia OFL (`public/fonts/LICENSES.txt`); no se añadieron dependencias.

**Mapa como instrumento.** Marcas de registro en las esquinas, retícula y curvas de nivel de fondo (la única superficie con retícula, porque representa coordenadas) y una leyenda que solo repite lo dibujado: trazo continuo IMERG, trazo discontinuo POWER y la ubicación generalizada de la parcela.

**Noche.** Nuevos tokens `--night-950/900/800` (azul verdoso profundo) para la barra, el héroe y el pie.

**Verificación.** axe sin violaciones WCAG 2.1 A/AA en las cuatro pantallas, sin desbordamiento horizontal a 375 y 768 px, 25 pruebas Playwright, 26 Vitest, ESLint, `tsc` y build en verde. El detector de Impeccable solo marca la retícula del mapa (advertencia consultiva).
