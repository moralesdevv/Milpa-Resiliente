/**
 * Content of the index section "Vision, scalability and roadmap".
 * Every line comes from the repository audit (docs/DATOS_FALTANTES.md, docs/FINAL_PROJECT_AUDIT.md,
 * docs/DATA_SOURCES.md, docs/ADD_A_REGION.md, ADR-004/007/008/015, catalogs/r2/*.yaml).
 * Rule: the vision never presents a plan as a capability. Each item says what exists today and what does not.
 */

export type Status = "Implemented" | "In Progress" | "Pending Validation" | "Future Development";
export type Priority = "Critical" | "High" | "Medium" | "Future";

export const CATEGORIES = [
  "Scientific validation",
  "Climate data infrastructure",
  "Agronomic calibration",
  "Field testing",
  "Institutional partnerships",
  "Backend and infrastructure",
  "Security and privacy",
  "Scalability",
  "User adoption and accessibility",
] as const;
export type Category = (typeof CATEGORIES)[number];

export type GapItem = {
  id: string;
  category: Category;
  title: string;
  missing: string;
  why: string;
  needed: string;
  who: string;
  priority: Priority;
  status: Status;
};

export const GAPS: readonly GapItem[] = [
  {
    id: "station-rain",
    category: "Scientific validation",
    title: "Camotán station history and local validation of satellite rainfall",
    missing: "No station series has been loaded, so every rainfall figure carries evidence level C. The comparison module (RMSE, bias, Pearson) is built and waits for real data.",
    why: "Exposure indicators, planting-date risk and the rainy-season onset estimate all rest on satellite and reanalysis rain that has not been checked against a gauge.",
    needed: "A daily precipitation series for the Camotán station (date, millimetres) with at least 365 days matching IMERG, then a review of the metrics by an agrometeorologist.",
    who: "INSIVUMEH (station records)",
    priority: "Critical",
    status: "Pending Validation",
  },
  {
    id: "stress-thresholds",
    category: "Scientific validation",
    title: "Validation of the water-stress models and thresholds",
    missing: "The three water-exposure thresholds are sandbox values calibrated on a synthetic series and carry no citation. Results are an exposure indicator, not soil water and not yield.",
    why: "Strategy rankings are only as meaningful as the thresholds that define a critical season at flowering and grain filling.",
    needed: "Cited thresholds for maize and bean critical stages, a root-zone water balance with cited rooting depth and depletion fraction, and a comparison with observed seasons.",
    who: "MAGA and ICTA agronomists; FAO-56 and the stress literature",
    priority: "Critical",
    status: "Pending Validation",
  },
  {
    id: "projections",
    category: "Scientific validation",
    title: "Climate projections instead of synthetic perturbations",
    missing: "The 45 scenarios are built by perturbing the historical record. NEX-GDDP-CMIP6 projections are not read by the pipeline.",
    why: "Perturbed history shows sensitivity; it does not describe how a territory's climate is expected to change.",
    needed: "An ETL connector for downscaled projections with provenance, a documented bias treatment and an ADR before any claim about future climate.",
    who: "NASA NCCS (NEX-GDDP-CMIP6); climate scientists",
    priority: "Future",
    status: "Future Development",
  },
  {
    id: "imerg-tail",
    category: "Climate data infrastructure",
    title: "IMERG beyond 30 September 2025",
    missing: "The IMERG series ends on 2025-09-30. NASA POWER fills the remaining days, so late-2025 rain has less satellite coverage.",
    why: "A gap-filled tail mixes two products with different resolution and bias.",
    needed: "A refreshed download with an Earthdata token and a repeatable, provenance-logged update run instead of manual command steps.",
    who: "NASA GES DISC (GPM IMERG); NASA Earthdata",
    priority: "High",
    status: "Future Development",
  },
  {
    id: "elevation-et0",
    category: "Climate data infrastructure",
    title: "One agreed elevation for evapotranspiration",
    missing: "The region file uses a reference elevation of 444.74 m for ET0 while the DEM zonal mean is 816 m and the POWER grid is 762 m.",
    why: "Elevation changes reference evapotranspiration, so the choice shifts every water-balance number.",
    needed: "A documented scientific decision on the representative elevation, then a re-frozen reproducibility fingerprint.",
    who: "Project science lead with INSIVUMEH station metadata",
    priority: "High",
    status: "Pending Validation",
  },
  {
    id: "nasa-sources",
    category: "Climate data infrastructure",
    title: "More Earth-observation layers",
    missing: "SMAP soil moisture, MODIS / HLS / Landsat vegetation and NEX-GDDP-CMIP6 are listed in the app as not integrated.",
    why: "Soil moisture and vegetation would let rain-based exposure be checked against what the land actually shows.",
    needed: "One validated ETL connector per source, each with provenance rows, evidence rules and tests.",
    who: "NASA Earthdata, NSIDC (SMAP), USGS / NASA LP DAAC",
    priority: "Medium",
    status: "Future Development",
  },
  {
    id: "kc-stages",
    category: "Agronomic calibration",
    title: "Kc and phenological stages for ICTA varieties",
    missing: "Stage durations and Kc are FAO-56 proxies scaled to each cycle. ICTA B-9 and B-15 publish no cycle or flowering data, and published values for ICTA B-7 disagree (95, 110, 120 days).",
    why: "The timing of the critical stages decides which days of rain matter.",
    needed: "Field phenology and Kc measurements per variety, or an ICTA review of the proxies, written into the rules file with citations.",
    who: "ICTA breeders; FAO-56 tables",
    priority: "Critical",
    status: "In Progress",
  },
  {
    id: "windows",
    category: "Agronomic calibration",
    title: "Official planting windows for Jocotán",
    missing: "The first-season (May 1 – Jun 30) and second-season (Aug 20 – Sep 30) windows are team test values, not official dates.",
    why: "A date is judged against its window. A wrong window makes a sound choice look risky, or the reverse.",
    needed: "A review of the windows against MAGA planting seasons and the local agroclimatic bulletin.",
    who: "MAGA (planting and harvest seasons, SCEP-MAGA Jocotán); Chiquimula agroclimatic bulletin",
    priority: "Critical",
    status: "Pending Validation",
  },
  {
    id: "soil-water",
    category: "Agronomic calibration",
    title: "Soil water capacity and rooting depth",
    missing: "SoilGrids gives texture estimates only. Available water capacity, effective depth and initial soil condition are not loaded, so the root-zone balance mode does not run.",
    why: "Without them the model reports rain exposure, not how much water a crop could actually reach.",
    needed: "Parcel soil tests or a soil map, plus cited rooting depth and depletion fraction per crop.",
    who: "MAGA and IGN soil maps; FAO-56; parcel soil analyses",
    priority: "High",
    status: "Pending Validation",
  },
  {
    id: "field-trials",
    category: "Field testing",
    title: "Field trials with technicians and farmers",
    missing: "Nothing has been tested with end users or on real parcels. There is no field evidence for any result.",
    why: "Only field use shows whether the comparisons are useful, understandable and right.",
    needed: "A trial protocol, willing parcels and cooperatives, informed consent, and a way to record what farmers actually did and saw.",
    who: "ICTA and MAGA extension staff; local cooperatives",
    priority: "Critical",
    status: "Future Development",
  },
  {
    id: "backtest",
    category: "Field testing",
    title: "Back-testing strategies against observed seasons",
    missing: "Strategy rankings have not been compared with what happened on real farms in past seasons.",
    why: "It is the test that separates a plausible ranking from a reliable one.",
    needed: "Parcel records across several seasons and an agreed definition of a bad year.",
    who: "Participating farmers and technicians; MAGA records",
    priority: "High",
    status: "Future Development",
  },
  {
    id: "insivumeh",
    category: "Institutional partnerships",
    title: "Data and method exchange with INSIVUMEH",
    missing: "There is no agreement. The onset estimator follows a criterion published in a MAGA bulletin and is labelled sandbox, not an INSIVUMEH method.",
    why: "Station data and the institution's own method are what would move rainfall evidence beyond level C.",
    needed: "A data-sharing arrangement for station records and a technical review of the onset criterion.",
    who: "INSIVUMEH",
    priority: "High",
    status: "Future Development",
  },
  {
    id: "territorial-data",
    category: "Institutional partnerships",
    title: "Versioned territorial datasets from MAGA, INAB and SEGEPLAN",
    missing: "Official references exist but are not ingested as versioned datasets. The municipal boundary's authorship is not declared in its file.",
    why: "Provenance for every layer is a rule of the project; a layer without an owner cannot meet it.",
    needed: "Agreed datasets with owner, version and licence, and an ETL step that records them.",
    who: "MAGA, INAB, SEGEPLAN, IGN",
    priority: "Medium",
    status: "Future Development",
  },
  {
    id: "repro",
    category: "Backend and infrastructure",
    title: "Reproducible runs and reports",
    missing: "Nothing for the pilot. Runs store region and data hashes, stale runs are refused, and the demo engine fingerprint is frozen.",
    why: "A result that cannot be reproduced cannot be reviewed by an institution.",
    needed: "Re-verify the fingerprint whenever a region, dataset or engine version changes.",
    who: "Project team",
    priority: "Medium",
    status: "Implemented",
  },
  {
    id: "refresh",
    category: "Backend and infrastructure",
    title: "Scheduled data refresh and verified container deployment",
    missing: "Data updates are manual command-line steps. The container image has not been verified since the latest engine changes; the demo runs from a host install.",
    why: "A platform that depends on someone remembering to rerun a script cannot stay current.",
    needed: "A scheduled ETL run with provenance, a built and smoke-tested image, and a documented hosting target.",
    who: "Project team; a hosting partner",
    priority: "High",
    status: "In Progress",
  },
  {
    id: "rls",
    category: "Security and privacy",
    title: "Row-level security and private coordinates",
    missing: "Nothing for the pilot. PostgreSQL row-level security, authorization on protected resources and generalised coordinates are implemented in the backend.",
    why: "Parcel data belongs to farmers; protection has to hold before real parcels are loaded.",
    needed: "Keep the privacy and isolation tests green as features are added.",
    who: "Project team",
    priority: "Medium",
    status: "Implemented",
  },
  {
    id: "privacy-review",
    category: "Security and privacy",
    title: "Independent security and privacy review",
    missing: "Consent, retention and privacy decisions (ADR-015) are still proposals. The public demo is anonymous, shares one zone and is rate-limited per address, with no per-session quota.",
    why: "Real parcels and real names need a reviewed policy, not a team decision.",
    needed: "Approval of the privacy ADRs, a legal review of Guatemalan data-protection duties, an external security test and per-session limits with demo clean-up.",
    who: "Legal and security reviewers; partner institutions",
    priority: "High",
    status: "Pending Validation",
  },
  {
    id: "second-region",
    category: "Scalability",
    title: "A second real territory",
    missing: "A new region is meant to be configuration files, not code, but only a synthetic test region exists. No second real territory has been added.",
    why: "Scaling is proven by onboarding another place with its own climate, elevation and crops.",
    needed: "A region file, a boundary, cited catalogs and local review for the next municipality, following the add-a-region guide.",
    who: "ICTA and MAGA regional offices; municipal technicians",
    priority: "High",
    status: "Future Development",
  },
  {
    id: "compute",
    category: "Scalability",
    title: "Processing for many regions and long histories",
    missing: "Jobs run in a process pool inside one application process with state in PostgreSQL, and results are Parquet files on local disk. This is single-node by design.",
    why: "Several regions, more strategies and multi-decade histories multiply the computation and the storage.",
    needed: "Benchmarks at multi-region scale, shared object storage if one node is not enough, and an ADR before adding any new infrastructure.",
    who: "Project team; a cloud or institutional host",
    priority: "Medium",
    status: "Future Development",
  },
  {
    id: "language",
    category: "User adoption and accessibility",
    title: "Spanish and plain-language use by farmers",
    missing: "The challenge demo is in English. Spanish text exists only in part, and no local-language support exists.",
    why: "The people who decide in the field read Spanish, and in Jocotán often Ch'orti' as well.",
    needed: "A complete Spanish interface, a plain reading of each result, and review by extension technicians and community members.",
    who: "MAGA extension; local organisations and translators",
    priority: "High",
    status: "Future Development",
  },
  {
    id: "usability",
    category: "User adoption and accessibility",
    title: "Usability testing and low-connectivity use",
    missing: "The interface is keyboard-operable, respects reduced motion and has 44 px targets, but it has not been tested with farmers or technicians and has no offline mode.",
    why: "Rural connections are slow and a tool that needs a desk will not be used in the field.",
    needed: "Moderated sessions with technicians and farmers, a lighter mobile view and offline reading of saved reports.",
    who: "Technicians, cooperatives and accessibility reviewers",
    priority: "Medium",
    status: "Future Development",
  },
];

export type Level = {
  id: string;
  index: string;
  name: string;
  place: string;
  state: "Built" | "Planned";
  summary: string;
  adds?: readonly string[];
  depends?: string;
  notClaimed: string;
};

export const LEVELS: readonly Level[] = [
  {
    id: "l1",
    index: "01",
    name: "Proof of concept",
    place: "Jocotán",
    state: "Built",
    summary: "The pilot you can launch today: one zone, real NASA series, a provisional science layer and every limit shown on the page.",
    notClaimed: "One pilot zone only. Parameters are provisional and rainfall is evidence level C.",
  },
  {
    id: "l2",
    index: "02",
    name: "Field validation",
    place: "Chiquimula",
    state: "Planned",
    summary: "Turn a convincing demo into a checked one: compare the satellite record with local observation and put the parameters in front of the agronomists.",
    adds: [
      "Historical INSIVUMEH station data loaded and compared with NASA POWER and IMERG",
      "Kc and phenological stages calibrated with ICTA",
      "Planting windows reviewed with MAGA and ICTA",
      "Tests with technicians and producers",
      "Strategies evaluated against real parcel information",
    ],
    depends: "Station records, institutional review and field partners. None of these is in place today.",
    notClaimed: "No institution has agreed to participate, and no validation has been done.",
  },
  {
    id: "l3",
    index: "03",
    name: "Regional expansion",
    place: "Guatemala",
    state: "Planned",
    summary: "Add territories one by one, each with its own configuration and review, and compare strategies between them.",
    adds: [
      "Municipalities and departments added progressively",
      "A region configuration per territory, with cited parameters",
      "More crops and varieties",
      "Different elevation, rainfall and temperature regimes",
      "Strategies compared across territories",
      "Links with agricultural institutions and organisations",
    ],
    depends: "Level 02 results, local agronomic review per territory and partners who maintain the parameters.",
    notClaimed: "No national coverage. A new region is meant to be configuration, but a second real territory has not been added.",
  },
  {
    id: "l4",
    index: "04",
    name: "Intelligence network",
    place: "National and regional",
    state: "Planned",
    summary: "An interoperable, documented infrastructure that institutions and researchers could build on, adapted locally wherever it is reused.",
    adds: [
      "Territorial agro-climate monitoring",
      "Evaluation of adaptation strategies over many years",
      "Multi-year historical analysis and simulation of future scenarios",
      "Station and field-sensor data alongside satellite records",
      "An API for institutions, researchers and agricultural organisations",
      "The method replicated in other Central American regions with local adaptation",
    ],
    depends: "Governance, funding, data agreements and infrastructure beyond one host. Today the API serves this app only.",
    notClaimed: "No integrations, agreements or users beyond this demo exist.",
  },
];

export const TODAY = {
  implemented: [
    "NASA POWER daily series and GPM IMERG V07B rainfall, 2001–2025, for the pilot cell",
    "Copernicus GLO-30 elevation and slope, SoilGrids estimates and the municipal boundary",
    "FAO-56 reference evapotranspiration from an open engine",
    "Seven strategies compared across 25 years and planting dates",
    "Planting-date check against documented FAO-56 and ICTA sources",
    "Evidence levels, SHA-256 provenance and reproducible PDF reports",
  ],
  simulated: [
    "45 synthetic climate scenarios built by perturbing the historical record. They are not projections",
    "A rainy-season onset estimator, labelled sandbox and not an INSIVUMEH product",
    "Water-stress exposure indicators. They are not soil water and not yield",
  ],
  pending: [
    "Satellite rainfall against a local station (level C today)",
    "Water-stress thresholds, which carry no citation yet",
    "Planting windows, Kc and stage durations (FAO-56 proxies where no ICTA data exist)",
    "Soil values, which are model estimates, not laboratory measurements",
  ],
} as const;

export const DIFFERENCES = [
  { head: "Decisions, not only maps", text: "Satellite and agronomic inputs become strategies you can compare side by side." },
  { head: "Many seasons, not one", text: "Each strategy is run over 25 years of record and 45 synthetic scenarios." },
  { head: "Resilient before best on average", text: "The comparison looks at how a strategy behaves in bad years and where objectives conflict." },
  { head: "Local knowledge in the loop", text: "ICTA varieties and MAGA planting seasons live in a rules file agronomists can edit, flagged provisional until they review it." },
  { head: "Uncertainty on the page", text: "Every figure shows its source, method and evidence level. An unknown value is never shown as zero." },
  { head: "Reproducible by design", text: "The same inputs give the same hashes and the same report." },
] as const;

export const POTENTIAL = [
  "Technicians could compare planting dates and rotations against a territory's own history before the season starts.",
  "Institutions could see where adaptation strategies hold up and where the evidence is still thin.",
  "Researchers could reuse the method in another territory by adding a region file and its cited parameters.",
  "Farmers could ask what happens if the rains start late and read the answer with its limits.",
] as const;

export const PRIORITIES: readonly Priority[] = ["Critical", "High", "Medium", "Future"];
export const STATUSES: readonly Status[] = ["Implemented", "In Progress", "Pending Validation", "Future Development"];
