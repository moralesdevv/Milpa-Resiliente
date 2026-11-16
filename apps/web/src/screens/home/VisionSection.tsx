import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import "./vision.css";
import {
  CATEGORIES,
  DIFFERENCES,
  GAPS,
  LEVELS,
  POTENTIAL,
  PRIORITIES,
  STATUSES,
  TODAY,
  type Category,
  type GapItem,
  type Level,
  type Priority,
  type Status,
} from "./visionData";

const slug = (value: string) => value.toLowerCase().replace(/[^a-z]+/g, "-");

/** Status tag: the meaning is carried by the words and a drawn shape, never by colour alone. */
function StatusTag({ status }: { status: Status }) {
  return <span className={`v-tag v-tag--${slug(status)}`}>{status}</span>;
}

function PriorityTag({ priority }: { priority: Priority }) {
  return <span className={`v-prio v-prio--${slug(priority)}`}>{priority}</span>;
}

/**
 * Schematic of territorial scope: nested rings, one per level. It is a diagram of ambition,
 * not a map: no real geometry, no coverage claim. Solid ring = built, dashed ring = planned.
 */
const RINGS = [
  { r: 30, label: "Jocotán" },
  { r: 80, label: "Chiquimula" },
  { r: 130, label: "Guatemala" },
  { r: 180, label: "Central America" },
] as const;

function ScopeDiagram({ active }: { active: number }) {
  return <figure className="vision-scope">
    <svg viewBox="0 0 400 400" role="img" aria-label={`Schematic of territorial scope. Level ${active + 1} of 4 selected: ${LEVELS[active].place}. Only the Jocotán ring is built.`}>
      <defs>
        <radialGradient id="vs-core" cx="50%" cy="50%" r="50%"><stop offset="0" stopColor="#ffd966" /><stop offset="1" stopColor="#e0a800" /></radialGradient>
      </defs>
      {[...RINGS].reverse().map((ring, reversed) => {
        const i = RINGS.length - 1 - reversed;
        const built = i === 0;
        const lit = i <= active;
        return <circle key={ring.label} cx="200" cy="200" r={ring.r}
          className={`vs-ring${built ? " is-built" : " is-planned"}${lit ? " is-lit" : ""}${i === active ? " is-active" : ""}`} />;
      })}
      <circle className="vs-pulse" cx="200" cy="200" r="30" />
      <circle cx="200" cy="200" r="11" fill="url(#vs-core)" />
      <g key={active} className="vs-orbiter" aria-hidden="true">
        <circle cx={200 + RINGS[active].r} cy="200" r="4.5" fill="#ffc933" />
      </g>
      {RINGS.map((ring, i) => <text key={ring.label} x="200" y={200 - ring.r - 7} textAnchor="middle"
        className={`vs-label${i === active ? " is-active" : ""}${i <= active ? " is-lit" : ""}`}>{ring.label}</text>)}
    </svg>
    <figcaption>Schematic of ambition, not a coverage map. Solid ring: built. Dashed rings: planned.</figcaption>
  </figure>;
}

function TodayColumns() {
  const columns = [
    { key: "implemented", head: "Implemented", note: "Real data, running in the demo", items: TODAY.implemented, status: "Implemented" as Status },
    { key: "simulated", head: "Simulated", note: "Computed on purpose, not observed", items: TODAY.simulated, status: "In Progress" as Status },
    { key: "pending", head: "Pending validation", note: "Provisional until reviewed", items: TODAY.pending, status: "Pending Validation" as Status },
  ];
  return <div className="vision-today">
    {columns.map((column) => <div key={column.key} className={`vision-today__col vision-today__col--${column.key}`}>
      <h5><span className={`v-tag v-tag--${slug(column.status)}`}>{column.head}</span></h5>
      <p className="vision-today__note">{column.note}</p>
      <ul>{column.items.map((item) => <li key={item}>{item}</li>)}</ul>
    </div>)}
  </div>;
}

function LevelPanel({ level }: { level: Level }) {
  return <div className="vision-panel">
    <p className="vision-panel__summary">{level.summary}</p>
    {level.id === "l1" && <TodayColumns />}
    {level.adds && <>
      <h5 className="vision-panel__h">What this level would add</h5>
      <ul className="vision-panel__list">{level.adds.map((item) => <li key={item}>{item}</li>)}</ul>
    </>}
    {level.depends && <p className="vision-panel__depends"><strong>Depends on.</strong> {level.depends}</p>}
    <p className="vision-panel__not"><strong>Not claimed.</strong> {level.notClaimed}</p>
  </div>;
}

function Levels() {
  const [active, setActive] = useState(0);
  return <section id="vision-levels" className="home-section vision-block" aria-labelledby="vision-levels-h">
    <h3 id="vision-levels-h" className="vision-h3">Four levels, one honest starting point</h3>
    <p className="vision-intro">Only Level 01 exists. The other three are a route, each one unlocked by data, validation and partners that this project does not have yet.</p>
    <div className="vision-levels">
      <ScopeDiagram active={active} />
      <ol className="vision-timeline">
        {LEVELS.map((level, i) => {
          const open = i === active;
          return <li key={level.id} className={`vision-step${open ? " is-open" : ""}${level.state === "Built" ? " is-built" : ""}`}>
            <h4>
              <button type="button" aria-expanded={open} aria-controls={`panel-${level.id}`} id={`tab-${level.id}`} onClick={() => setActive(i)}>
                <span className="vision-step__node" aria-hidden="true" />
                <span className="vision-step__index">Level {level.index}</span>
                <span className="vision-step__name">{level.name}: {level.place}</span>
                <span className={`v-state v-state--${level.state.toLowerCase()}`}>{level.state}</span>
              </button>
            </h4>
            <div id={`panel-${level.id}`} role="region" aria-labelledby={`tab-${level.id}`} hidden={!open}>
              {open && <LevelPanel level={level} />}
            </div>
          </li>;
        })}
      </ol>
    </div>
  </section>;
}

function Why() {
  return <section id="vision-why" className="home-section vision-block" aria-labelledby="vision-why-h">
    <div className="vision-why">
      <div>
        <h3 id="vision-why-h" className="vision-h3">Why does MILPA RESILIENTE matter?</h3>
        <p className="vision-body">Farming in Guatemala&rsquo;s Dry Corridor depends on rain that can arrive late, stop early or fall in the wrong week. Territories differ widely in elevation, rainfall and soil, so what works in one valley may fail in the next.</p>
        <p className="vision-body">A planting or rotation decision has to weigh more than the current season: how a strategy behaved across many past years, what each crop needs at its critical stages, and how uncertain the evidence is.</p>
        <p className="vision-body vision-body--lead">Climate maps show what happened. This project asks a different question: which strategies keep working when the year goes wrong?</p>
      </div>
      <ul className="vision-diff">
        {DIFFERENCES.map((item) => <li key={item.head}><strong>{item.head}</strong><span>{item.text}</span></li>)}
      </ul>
    </div>
    <p className="home-note vision-honest">No gain in yield, reduction in losses or change in income is claimed. None of these has been measured in the field.</p>
  </section>;
}

function Summary({ items }: { items: readonly GapItem[] }) {
  const counts = STATUSES.map((status) => ({ status, n: items.filter((item) => item.status === status).length }));
  const total = items.length;
  const label = counts.map(({ status, n }) => `${n} ${status}`).join(", ");
  return <div className="vision-summary">
    <div className="vision-bar" role="img" aria-label={`${total} gaps: ${label}`}>
      {counts.filter(({ n }) => n > 0).map(({ status, n }) => <span key={status} className={`vision-bar__seg v-seg--${slug(status)}`} style={{ flexGrow: n }} />)}
    </div>
    <ul className="vision-legend">
      {counts.map(({ status, n }) => <li key={status}><StatusTag status={status} /> <b>{n}</b></li>)}
    </ul>
  </div>;
}

function Roadmap() {
  const [category, setCategory] = useState<Category | "All">("All");
  const [priority, setPriority] = useState<Priority | "All">("All");
  const visible = useMemo(() => GAPS.filter((item) => (category === "All" || item.category === category) && (priority === "All" || item.priority === priority)), [category, priority]);
  const groups = CATEGORIES.map((name) => ({ name, items: visible.filter((item) => item.category === name) })).filter((group) => group.items.length > 0);
  const countIn = (name: Category) => GAPS.filter((item) => item.category === name).length;

  return <section id="vision-roadmap" className="home-section vision-block" aria-labelledby="vision-roadmap-h">
    <h3 id="vision-roadmap-h" className="vision-h3">What is needed to reach 100%</h3>
    <p className="vision-intro">{GAPS.length} concrete gaps found by auditing the code, data catalogs, architecture decisions and documentation. Each says what is missing, why it matters, what would close it and who could help. Nothing here is a capability today unless it is marked Implemented.</p>
    <Summary items={GAPS} />

    <div className="vision-filters" role="group" aria-label="Filter the roadmap by category">
      <button type="button" className="v-chip" aria-pressed={category === "All"} onClick={() => setCategory("All")}>All <span>{GAPS.length}</span></button>
      {CATEGORIES.map((name) => <button key={name} type="button" className="v-chip" aria-pressed={category === name} onClick={() => setCategory(name)}>{name} <span>{countIn(name)}</span></button>)}
    </div>
    <div className="vision-filters vision-filters--prio" role="group" aria-label="Filter the roadmap by priority">
      <span className="vision-filters__label">Priority</span>
      {(["All", ...PRIORITIES] as const).map((name) => <button key={name} type="button" className="v-chip v-chip--small" aria-pressed={priority === name} onClick={() => setPriority(name)}>{name}</button>)}
    </div>

    <div className="vision-gaps" aria-live="polite">
      {groups.length === 0 && <p className="vision-empty">No gaps match these filters. <button type="button" className="v-link" onClick={() => { setCategory("All"); setPriority("All"); }}>Show all gaps</button></p>}
      {groups.map((group) => <div key={group.name} className="vision-group">
        <h4>{group.name}</h4>
        {group.items.map((item) => <details key={item.id} className="vision-gap">
          <summary>
            <span className="vision-gap__title">{item.title}</span>
            <span className="vision-gap__tags"><PriorityTag priority={item.priority} /><StatusTag status={item.status} /></span>
          </summary>
          <dl>
            <div><dt>What is missing</dt><dd>{item.missing}</dd></div>
            <div><dt>Why it matters</dt><dd>{item.why}</dd></div>
            <div><dt>What is needed</dt><dd>{item.needed}</dd></div>
            <div><dt>Who could help</dt><dd>{item.who}</dd></div>
          </dl>
        </details>)}
      </div>)}
    </div>
  </section>;
}

function Potential() {
  return <section id="vision-potential" className="home-section vision-block" aria-labelledby="vision-potential-h">
    <h3 id="vision-potential-h" className="vision-h3">If it is completed and validated</h3>
    <p className="vision-intro">A hypothesis about what the platform could become. It is not a result, and nothing below has been measured.</p>
    <ul className="vision-potential">
      {POTENTIAL.map((text) => <li key={text}>{text}</li>)}
    </ul>
  </section>;
}

function Closing() {
  return <section className="home-section vision-closing" aria-labelledby="vision-closing-h">
    <h3 id="vision-closing-h" className="vision-sr">A message for the jury</h3>
    <blockquote>
      <p><strong>MILPA RESILIENTE</strong> begins with a pilot in Jocotán, but its ambition goes beyond a single territory: turning Earth observation, agricultural science and local knowledge into better-informed climate adaptation decisions for farming communities.</p>
    </blockquote>
    <div className="home-actions">
      <Link className="home-cta home-cta--solid" to="/demo">Launch demo</Link>
      <a className="home-cta home-cta--ghost" href="#vision">Back to the vision</a>
    </div>
  </section>;
}

export function VisionSection() {
  return <div className="vision" id="vision">
    <section className="home-section vision-lead" aria-labelledby="vision-title">
      <h2 id="vision-title" className="vision-title">From a local pilot to a national climate-resilient <em>agricultural intelligence network.</em></h2>
      <p className="vision-sub">MILPA RESILIENTE is not meant to stay a planting calendar or a satellite viewer. The ambition is to connect NASA Earth observation, weather and climate records, local agronomic knowledge, adapted Guatemalan varieties, scenario modelling and station validation, so that agricultural decisions rest on evidence. The demo shows what is built. This section shows where it could go, and what stands in the way.</p>
    </section>
    <Why />
    <Levels />
    <Roadmap />
    <Potential />
    <Closing />
  </div>;
}
