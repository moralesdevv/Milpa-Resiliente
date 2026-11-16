import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import { BrandMark } from "../components/common/Icon";
import { VisionSection } from "./home/VisionSection";

/**
 * Entry point of the application ("index").
 * A full-bleed view of the Earth from orbit, a sticky pill navigation with the LAUNCH DEMO call to
 * action, a headline set in Funnel Display whose lines rise into place, and a mission plate that
 * states, without embellishment, which NASA Space Apps challenge this answers and what data feeds it.
 * The imagery is generated SVG/CSS (decorative, aria-hidden): it never represents measurements or real locations.
 */
export const EXPERIENCES = [
  { to: "/mvp", name: "MVP workspace", text: "Everything in one place: data sources, 25-year climate, strategy comparison, planting calendar, limits." },
  { to: "/my-zone", name: "My zone", text: "Where you are planting: the climate cell, terrain and the data behind it." },
  { to: "/calendar", name: "How the calendar changed", text: "25 years of rain and heat, planting-date heat-maps and the dekad-by-dekad water picture." },
  { to: "/rotations", name: "Rotation lab", text: "Compare crop associations and rotations, stress-test them with 45 synthetic climate scenarios." },
  { to: "/report", name: "Decision report", text: "A report that shows the ranking, the evidence level of every figure and what is still unknown." },
  { to: "/plants", name: "Plants", text: "The crops in each strategy, their growth stages and the stages where water stress matters." },
] as const;

const SOURCES = [
  { name: "NASA POWER", detail: "Daily temperature, humidity, wind, radiation and rainfall (MERRA-2 / CERES), 2001–2025" },
  { name: "NASA GPM IMERG", detail: "Satellite rainfall at 0.1° (Final Run V07) where an Earthdata token is available" },
  { name: "FAO-56", detail: "Penman–Monteith reference evapotranspiration computed by the open scientific engine" },
  { name: "Evidence level", detail: "Every figure keeps its source and method, and is labelled A, B or C for how well it is supported" },
] as const;

const YEARS = Array.from({ length: 25 }, (_, i) => 2001 + i);
const RULER_LABELS = new Set([2001, 2007, 2013, 2019, 2025]);

/** Drawn arrow (one stroke weight across the page) instead of a text glyph. */
function Arrow() {
  return <svg className="home-arrow" width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true" focusable="false">
    <path d="M4 10h11M10.5 5l5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>;
}

/** 2001 to 2025, one tick per year: the length of the NASA record the whole site reads from. */
function YearRuler() {
  return <div className="home-ruler" role="img" aria-label="Twenty-five years of NASA daily records, 2001 to 2025">
    <ol aria-hidden="true">
      {YEARS.map((year, i) => <li key={year} className={RULER_LABELS.has(year) ? "is-major" : undefined} style={{ "--i": i } as CSSProperties}>
        {RULER_LABELS.has(year) ? <span>{year}</span> : null}
      </li>)}
    </ol>
  </div>;
}

function Backdrop() {
  // Deterministic star field and cropland mosaic: the same picture on every render.
  const stars = Array.from({ length: 70 }, (_, i) => ({ x: (i * 197) % 1600, y: (i * 89 + (i % 7) * 41) % 560, r: 0.5 + (i % 3) * 0.45, o: 0.25 + (i % 5) * 0.12 }));
  const fields = ["#1d6b46", "#2f8f53", "#8fb43c", "#c9a227", "#9c5a26", "#0f4f3a", "#3a9d6a", "#d8b552"];
  const patches = Array.from({ length: 42 }, (_, i) => ({
    x: 930 + (i % 7) * 118 + ((Math.floor(i / 7) * 37) % 60),
    y: 520 + Math.floor(i / 7) * 74 + ((i * 13) % 22),
    w: 84 + ((i * 17) % 38), h: 40 + ((i * 11) % 28), c: fields[i % fields.length],
  }));
  return <svg className="home-backdrop" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
    <defs>
      <radialGradient id="home-sky" cx="70%" cy="105%" r="90%"><stop offset="0" stopColor="#0d3b52" /><stop offset=".45" stopColor="#071d2b" /><stop offset="1" stopColor="#030d14" /></radialGradient>
      <radialGradient id="home-glow" cx="50%" cy="50%" r="50%"><stop offset=".78" stopColor="#4fd1c5" stopOpacity="0" /><stop offset=".93" stopColor="#4fd1c5" stopOpacity=".45" /><stop offset="1" stopColor="#4fd1c5" stopOpacity="0" /></radialGradient>
      <clipPath id="home-globe"><circle cx="1230" cy="1480" r="980" /></clipPath>
    </defs>
    <rect width="1600" height="900" fill="url(#home-sky)" />
    {stars.map((s, i) => <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#fff" opacity={s.o} />)}
    <circle cx="1230" cy="1480" r="1040" fill="url(#home-glow)" />
    <g clipPath="url(#home-globe)">
      <circle cx="1230" cy="1480" r="980" fill="#0e6a73" />
      <path d="M0 640 C 600 560 900 520 1230 540 S 1650 600 1800 650 V 900 H0 Z" fill="#1a7a4e" opacity=".9" />
      {patches.map((p, i) => <rect key={i} x={p.x} y={p.y} width={p.w} height={p.h} rx="6" fill={p.c} opacity=".85" transform={`skewX(-14) translate(${p.y * 0.25},0)`} />)}
      <circle cx="1230" cy="1480" r="980" fill="none" stroke="#7be0d4" strokeOpacity=".5" strokeWidth="2" />
    </g>
    <ellipse className="home-orbit" cx="860" cy="470" rx="760" ry="215" transform="rotate(-9 860 470)" fill="none" stroke="#9ee8de" strokeOpacity=".28" strokeDasharray="3 9" />
    <circle className="home-satellite" r="5" fill="#ffc933">
      <animateMotion dur="38s" repeatCount="indefinite" path="M 100 520 A 760 215 -9 1 1 1620 420 A 760 215 -9 1 1 100 520" />
    </circle>
  </svg>;
}

/** Maize seedlings along the lower edge; the leaves sway gently (disabled for reduced motion). */
function Seedlings() {
  const plants = [60, 190, 330, 1180, 1320, 1460].map((x, i) => ({ x, h: 120 + (i % 3) * 38, d: i * 0.7 }));
  return <svg className="home-seedlings" viewBox="0 0 1600 220" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
    {plants.map((p) => <g key={p.x} className="home-plant" style={{ animationDelay: `${p.d}s` }} transform={`translate(${p.x} 220)`}>
      <path d={`M0 0 V ${-p.h}`} stroke="#6fbf73" strokeWidth="5" strokeLinecap="round" />
      <path d={`M0 ${-p.h * 0.35} C 40 ${-p.h * 0.5} 78 ${-p.h * 0.42} 96 ${-p.h * 0.18}`} stroke="#8fd18b" strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d={`M0 ${-p.h * 0.6} C -42 ${-p.h * 0.78} -80 ${-p.h * 0.7} -100 ${-p.h * 0.44}`} stroke="#8fd18b" strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d={`M0 ${-p.h * 0.82} C 28 ${-p.h * 0.98} 58 ${-p.h * 0.96} 74 ${-p.h * 0.78}`} stroke="#b7e08a" strokeWidth="4" fill="none" strokeLinecap="round" />
    </g>)}
  </svg>;
}

export function HomeScreen() {
  return <div className="home">
    <a className="skip-link" href="#home-content">Skip to content</a>
    <header className="home-nav">
      <Link className="home-nav__brand" to="/" aria-label="MILPA RESILIENTE home">
        <span className="home-nav__mark"><BrandMark /></span>
        <span className="home-nav__word">Milpa<br />Resiliente</span>
      </Link>
      <nav className="home-nav__links" aria-label="Main navigation">
        <Link to="/mvp">MVP</Link>
        <Link to="/plants">Plants</Link>
        <Link to="/my-zone">My zone</Link>
        <Link to="/calendar">Calendar</Link>
        <Link to="/rotations">Rotation lab</Link>
        <Link to="/report">Report</Link>
        <a href="#vision">Vision</a>
      </nav>
      <Link className="home-cta home-cta--pill" to="/demo">Launch demo</Link>
    </header>

    <section className="home-hero" aria-labelledby="home-title">
      <Backdrop />
      <Seedlings />
      <div className="home-veil" aria-hidden="true" />
      <div className="home-hero__copy">
        <h1 id="home-title" className="home-title">
          <span className="home-line"><span style={{ "--i": 0 } as CSSProperties}>The next harvest</span></span>{" "}
          <span className="home-line"><span style={{ "--i": 1 } as CSSProperties}>starts with <em className="home-title__sky">the sky.</em></span></span>
        </h1>
        <p className="home-lede">Compare planting dates and crop rotations against 25 years of NASA climate data. See the risk, the trade-offs and the evidence behind every number — and what we still do not know.</p>
        <div className="home-actions">
          <Link className="home-cta home-cta--solid" to="/demo">Launch demo</Link>
          <a className="home-cta home-cta--ghost" href="#home-content">Explore the tools</a>
        </div>
        <YearRuler />
        <dl className="home-plate">
          <div><dt>Challenge</dt><dd><strong>NASA Space Apps Challenge</strong>Field Shift: Adapting Farms with NASA Data</dd></div>
          <div><dt>NASA data</dt><dd><strong>POWER daily · GPM IMERG</strong>2001–2025, read by an open scientific engine</dd></div>
          <div><dt>Pilot</dt><dd><strong>Jocotán, Chiquimula</strong>Provisional parameters · not a forecast</dd></div>
        </dl>
      </div>
    </section>

    <section id="home-content" className="home-section" aria-labelledby="home-tools">
      <h2 id="home-tools" className="home-h2 home-reveal">Six ways into the same evidence</h2>
      <ol className="home-list home-reveal">
        {EXPERIENCES.map((item) => <li key={item.to}>
          <Link to={item.to} className="home-row">
            <span className="home-row__name">{item.name}</span>
            <span className="home-row__text">{item.text}</span>
            <span className="home-row__go"><code>{item.to}</code><Arrow /></span>
          </Link>
        </li>)}
      </ol>
    </section>

    <section className="home-section home-section--dark" aria-labelledby="home-evidence">
      <h2 id="home-evidence" className="home-h2 home-reveal">Every figure carries its source, method and evidence level</h2>
      <p className="home-intro home-reveal">Built for the NASA Space Apps Challenge <em>Field Shift: Adapting Farms with NASA Data</em>. Two NASA products feed the pilot; one open standard turns them into water demand; each result keeps its trail.</p>
      <ol className="home-lineage home-reveal">
        {SOURCES.map((source) => <li key={source.name}><strong>{source.name}</strong><p>{source.detail}</p></li>)}
      </ol>
      <p className="home-note home-reveal">Scenarios are synthetic and are not forecasts. Results are an exposure indicator, not a prediction of yield, and are provisional until validated with local weather stations and agronomic review.</p>
    </section>

    <VisionSection />

    <footer className="home-footer">
      <span><strong>MILPA RESILIENTE 3.3</strong> · Built for the NASA Space Apps Challenge, Field Shift: Adapting Farms with NASA Data</span>
      <span>An independent project: not affiliated with or endorsed by NASA. Not an automatic recommendation · Not an expected-yield estimate</span>
    </footer>
  </div>;
}
