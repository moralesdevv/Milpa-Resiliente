/**
 * Ilustración geométrica del encabezado de cada módulo: el limbo de la Tierra visto desde órbita,
 * con un mosaico de parcelas agrícolas, curvas de nivel, la atmósfera y un satélite en órbita.
 * Es solo decoración (aria-hidden) y no representa datos ni ubicaciones reales.
 * El color de acento lo fija cada módulo mediante `--accent`.
 */
const EARTH = { cx: 1180, cy: 1010, r: 720 } as const;

/** Elipse como trazado cerrado (cuatro curvas de Bézier), girada `deg` grados. */
function ellipsePath(cx: number, cy: number, rx: number, ry: number, deg: number): string {
  const k = 0.5522847498;
  const rad = (deg * Math.PI) / 180;
  const rot = (x: number, y: number) => `${(cx + x * Math.cos(rad) - y * Math.sin(rad)).toFixed(1)} ${(cy + x * Math.sin(rad) + y * Math.cos(rad)).toFixed(1)}`;
  return [
    `M ${rot(rx, 0)}`,
    `C ${rot(rx, ry * k)} ${rot(rx * k, ry)} ${rot(0, ry)}`,
    `C ${rot(-rx * k, ry)} ${rot(-rx, ry * k)} ${rot(-rx, 0)}`,
    `C ${rot(-rx, -ry * k)} ${rot(-rx * k, -ry)} ${rot(0, -ry)}`,
    `C ${rot(rx * k, -ry)} ${rot(rx, -ry * k)} ${rot(rx, 0)} Z`,
  ].join(" ");
}

const ORBIT = ellipsePath(1180, 470, 780, 235, -9);

const FIELD_COLOURS = ["#0f9966", "#35c26a", "#b7d94c", "#ffc933", "#b8501f", "#0a5a3c", "#1ea66f", "#e8b94a"];

/** Mosaico determinista de parcelas (sin azar: siempre se dibuja igual). */
const FIELDS = Array.from({ length: 34 }, (_, i) => {
  const col = i % 9;
  const row = Math.floor(i / 9);
  const x = 700 + col * 112 + (row % 2) * 46 + ((i * 37) % 23);
  const y = 296 + row * 46 + ((i * 53) % 17);
  const w = 74 + ((i * 29) % 52);
  const h = 30 + ((i * 41) % 26);
  return { id: i, x, y, w, h, tilt: -14 + ((i * 17) % 28), fill: FIELD_COLOURS[(i * 5 + row) % FIELD_COLOURS.length], opacity: 0.55 + ((i * 7) % 4) * 0.1 };
});

const STARS = Array.from({ length: 26 }, (_, i) => ({
  id: i,
  x: 40 + ((i * 211) % 1500),
  y: 18 + ((i * 97) % 250),
  r: i % 5 === 0 ? 1.8 : 1.1,
  o: 0.25 + ((i * 13) % 6) * 0.1,
}));

export function HeroArt() {
  return <svg className="hero-art" viewBox="0 0 1600 460" preserveAspectRatio="xMaxYMax slice" aria-hidden="true" focusable="false">
    <defs>
      <clipPath id="hero-earth-clip"><circle cx={EARTH.cx} cy={EARTH.cy} r={EARTH.r} /></clipPath>
    </defs>
    <g fill="#fbf3dc">{STARS.map((star) => <circle key={star.id} cx={star.x} cy={star.y} r={star.r} opacity={star.o} />)}</g>
    <path d={ORBIT} fill="none" stroke="#fbf3dc" strokeOpacity="0.28" strokeWidth="1.4" strokeDasharray="2 9" strokeLinecap="round" />
    <g className="hero-art__atmosphere" fill="none" stroke="currentColor">
      <circle cx={EARTH.cx} cy={EARTH.cy} r={EARTH.r + 30} strokeOpacity="0.1" strokeWidth="44" />
      <circle cx={EARTH.cx} cy={EARTH.cy} r={EARTH.r + 12} strokeOpacity="0.28" strokeWidth="16" />
      <circle cx={EARTH.cx} cy={EARTH.cy} r={EARTH.r + 3} strokeOpacity="0.95" strokeWidth="3" />
    </g>
    <circle cx={EARTH.cx} cy={EARTH.cy} r={EARTH.r} fill="#0a3f2c" />
    <g clipPath="url(#hero-earth-clip)">
      {FIELDS.map((field) => <rect key={field.id} x={field.x} y={field.y} width={field.w} height={field.h} rx="3" fill={field.fill} opacity={field.opacity} transform={`rotate(${field.tilt} ${field.x + field.w / 2} ${field.y + field.h / 2})`} />)}
      <image href="/brand/topo-dark.svg" x="620" y="250" width="1100" height="440" opacity="0.5" preserveAspectRatio="xMidYMid slice" />
      <circle cx={EARTH.cx} cy={EARTH.cy} r={EARTH.r} fill="none" stroke="#04261b" strokeOpacity="0.55" strokeWidth="60" />
    </g>
    <g className="hero-art__satellite" style={{ offsetPath: `path("${ORBIT}")` }}>
      <rect x="-9" y="-3" width="18" height="6" rx="1.5" fill="#fbf3dc" />
      <rect x="-26" y="-5" width="14" height="10" rx="1" fill="currentColor" />
      <rect x="12" y="-5" width="14" height="10" rx="1" fill="currentColor" />
    </g>
  </svg>;
}
