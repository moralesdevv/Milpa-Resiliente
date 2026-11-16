/**
 * Icon set of the interface: one consistent 1.75px outline stroke on a 24px grid.
 * Purely presentational. Always rendered aria-hidden: the heading next to it names the section.
 */
const paths = {
  /** Location / territory */
  location: <><path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z" /><circle cx="12" cy="10" r="2.4" /></>,
  /** Crop / maize leaf */
  crop: <><path d="M12 21V8" /><path d="M12 13c-3.6 0-5.6-2.2-6-6 3.6 0 5.8 2 6 6Z" /><path d="M12 10c0-3.4 1.8-5.6 5.6-6 .2 3.8-1.8 6-5.6 6Z" /><path d="M12 17.5c3 0 4.8-1.7 5.2-4.8-3 0-4.9 1.6-5.2 4.8Z" /></>,
  /** Sources / data provenance */
  source: <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" /><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></>,
  /** Soil layers */
  soil: <><path d="M3 8.5 12 4l9 4.5-9 4.5L3 8.5Z" /><path d="m3 12.5 9 4.5 9-4.5" /><path d="m3 16.5 9 4.5 9-4.5" /></>,
  /** Question / value of information */
  question: <><circle cx="12" cy="12" r="9" /><path d="M9.6 9.4a2.5 2.5 0 1 1 3.6 2.2c-.8.5-1.2 1-1.2 1.9" /><path d="M12 17h.01" /></>,
  /** Search / filters */
  filter: <><path d="M4 5h16l-6.2 7.4V19l-3.6-1.8v-4.8L4 5Z" /></>,
  /** Climate history / clock */
  history: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.2 2" /></>,
  /** Risk table / bars */
  risk: <><path d="M4 20V10" /><path d="M10 20V4" /><path d="M16 20v-7" /><path d="M21 20H3" /></>,
  /** Comparison / arrows */
  compare: <><path d="M4 8h14" /><path d="m14 4 4 4-4 4" /><path d="M20 16H6" /><path d="m10 12-4 4 4 4" /></>,
  /** Catalog / list */
  list: <><path d="M9 6h11" /><path d="M9 12h11" /><path d="M9 18h11" /><path d="M4.5 6h.01" /><path d="M4.5 12h.01" /><path d="M4.5 18h.01" /></>,
  /** Jobs / gear */
  gear: <><circle cx="12" cy="12" r="3" /><path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" /></>,
  /** Weights / sliders */
  sliders: <><path d="M4 7h9" /><path d="M17 7h3" /><circle cx="15" cy="7" r="2" /><path d="M4 17h3" /><path d="M11 17h9" /><circle cx="9" cy="17" r="2" /></>,
  /** Report / document */
  document: <><path d="M7 3h7l5 5v13H7V3Z" /><path d="M14 3v5h5" /><path d="M10 13h6M10 17h6" /></>,
  /** Warning / provisional */
  alert: <><path d="M12 4 3 19h18L12 4Z" /><path d="M12 10v4" /><path d="M12 17h.01" /></>,
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {paths[name]}
  </svg>;
}

/** Brand mark: a maize stalk whose two leaves also trace the letter M. */
export function BrandMark() {
  return <svg className="brand__svg" width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
    <path d="M4 20V8.5c0-1 1.2-1.5 1.9-.8L12 14l6.1-6.3c.7-.7 1.9-.2 1.9.8V20" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M12 14V4" stroke="var(--maize-400)" strokeWidth="2.2" strokeLinecap="round" />
  </svg>;
}
