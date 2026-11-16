/**
 * Integration status of every data source the project contemplates. Maintained by hand from
 * docs/DATA_SOURCES.md: a source is listed as "Integrated" only if the pipeline actually reads it.
 */
type Status = "integrated" | "available" | "not-integrated";
const SOURCES: { name: string; role: string; status: Status; note: string; url: string }[] = [
  { name: "NASA POWER (daily)", role: "Temperature, humidity, wind, radiation, rainfall", status: "integrated", note: "Downloaded and curated for the pilot zone, 2001–2025. Coarse reanalysis; not a station observation.", url: "https://power.larc.nasa.gov/docs/services/api/temporal/daily/" },
  { name: "NASA GPM IMERG daily V07B", role: "Satellite rainfall, 0.1°", status: "integrated", note: "camotan_jocotan: 2001-01-01 to 2025-09-30. POWER fills gaps/out-of-period. Not validated against a local station (evidence C). Other zones require NASA Earthdata and GES DISC authorization.", url: "https://gpm.nasa.gov/data/directory" },
  { name: "Copernicus GLO-30 DEM (ESA)", role: "Elevation and slope", status: "integrated", note: "Zonal mean elevation (816 m) and slope (39 %) of the analysis cell computed from the GLO-30 raster with the project DEM loader and registered with provenance. The ET0 calculation still uses the reference-point elevation of the region pack.", url: "https://registry.opendata.aws/copernicus-dem/" },
  { name: "SMAP", role: "Soil moisture", status: "not-integrated", note: "Not read by the pipeline. Shown for scope only.", url: "https://nsidc.org/data/smap" },
  { name: "MODIS / HLS / Landsat 8-9", role: "Vegetation and land surface", status: "not-integrated", note: "Not read by the pipeline. NASA/USGS access may require Earthdata credentials and a separate validated ETL.", url: "https://search.earthdata.nasa.gov/" },
  { name: "NEX-GDDP-CMIP6", role: "Climate projections", status: "not-integrated", note: "Not read. Scenarios in this app are synthetic perturbations of historical data, not projections.", url: "https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6" },
  { name: "SoilGrids (ISRIC)", role: "Soil properties (estimates)", status: "integrated", note: "Mean of three sample points inside the municipality, 0–5 cm, fetched from the ISRIC REST service by the project ETL (tools/etl_soilgrids.py). Model estimates, not laboratory measurements; shown apart from field data (evidence C).", url: "https://rest.isric.org/soilgrids/v2.0/docs" },
  { name: "MAGA · INAB · SEGEPLAN (Guatemala)", role: "Crop calendars, forest and territorial data", status: "available", note: "Official references are available; they are not yet ingested as a versioned dataset. MAGA sowing seasons are national/regional context, not parcel-level validation.", url: "https://www.maga.gob.gt/download/epocas-siembra-cosecha-agricolas-guatemala.pdf" },
];
const LABEL: Record<Status, string> = { integrated: "Integrated", available: "Implemented, needs credentials or data", "not-integrated": "Not integrated" };

export function SourceStatus() {
  return <div className="table-scroll"><table className="data-table source-status" data-testid="source-status">
    <caption>Data sources and their real integration status</caption>
    <thead><tr><th scope="col">Source</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col">Notes</th></tr></thead>
    <tbody>{SOURCES.map((source) => <tr key={source.name}>
      <th scope="row">{source.name}</th><td>{source.role}</td>
      <td><span className={`status-chip source-status__chip source-status__chip--${source.status}`}>{LABEL[source.status]}</span></td>
      <td>{source.note} <a href={source.url} target="_blank" rel="noreferrer">Source / download</a></td>
    </tr>)}</tbody>
  </table></div>;
}
