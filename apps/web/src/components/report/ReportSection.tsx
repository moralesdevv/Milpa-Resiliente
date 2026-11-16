/**
 * One section of the backend report (the same ReportInput the PDF is drawn from): title, body, bullet
 * items and an optional table. Text arrives in Spanish (`*_es`) and English (`*_en`); the interface
 * language picks one. Nothing is calculated here.
 */
export type ReportSectionData = Record<string, unknown>;

export type ReportTableView = { caption: string | null; headers: string[]; rows: string[][]; weights: number[] | null };

function text(section: ReportSectionData, key: string): string | null {
  const value = section[key];
  return typeof value === "string" && value ? value : null;
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

export function readTable(section: ReportSectionData, english: boolean): ReportTableView | null {
  const raw = section.table;
  if (typeof raw !== "object" || raw === null) return null;
  const table = raw as Record<string, unknown>;
  const headers = strings(table.headers);
  if (headers.length === 0) return null;
  const rows = Array.isArray(table.rows) ? table.rows.map(strings).filter((row) => row.length === headers.length) : [];
  const weights = Array.isArray(table.weights) && table.weights.length === headers.length && table.weights.every((w) => typeof w === "number" && w > 0)
    ? (table.weights as number[])
    : null;
  const caption = (english ? text(table, "caption_en") : text(table, "caption_es")) ?? text(table, "caption_es");
  return { caption, headers, rows, weights };
}

/** Bilingual tables carry "es / en" in headers and cells; the interface language shows its own half. */
export function pickLanguage(value: string, english: boolean): string {
  const parts = value.split(" / ");
  if (parts.length !== 2) return value;
  return english ? parts[1] : parts[0];
}

export function ReportTable({ table, english }: { table: ReportTableView; english: boolean }) {
  const total = table.weights?.reduce((sum, w) => sum + w, 0) ?? 0;
  return <div className="table-scroll report-table-scroll">
    <table className="data-table report-table" data-testid="report-table">
      {table.caption && <caption>{table.caption}</caption>}
      {table.weights && <colgroup>{table.weights.map((w, index) => <col key={index} style={{ width: `${(100 * w / total).toFixed(1)}%` }} />)}</colgroup>}
      <thead><tr>{table.headers.map((header, index) => <th scope="col" key={index}>{pickLanguage(header, english)}</th>)}</tr></thead>
      <tbody>{table.rows.map((row, rowIndex) => <tr key={rowIndex}>
        {row.map((cell, cellIndex) => cellIndex === 0
          ? <th scope="row" key={cellIndex}>{pickLanguage(cell, english)}</th>
          : <td key={cellIndex}>{pickLanguage(cell, english)}</td>)}
      </tr>)}</tbody>
    </table>
  </div>;
}

export function ReportSectionBlock({ section, english, fallbackTitle }: { section: ReportSectionData; english: boolean; fallbackTitle: string }) {
  const title = (english ? text(section, "title_en") : text(section, "title_es")) ?? text(section, "title_es") ?? text(section, "title") ?? fallbackTitle;
  const body = (english ? text(section, "body_en") : text(section, "body_es")) ?? text(section, "body_es");
  const items = english && strings(section.items_en).length > 0 ? strings(section.items_en) : strings(section.items);
  const table = readTable(section, english);
  return <article className="report-section" data-testid="report-section">
    <h4>{title}</h4>
    {body && <p>{body}</p>}
    {items.length > 0 && <ul className="report-section__items">{items.map((item, index) => <li key={index}>{item}</li>)}</ul>}
    {table && <ReportTable table={table} english={english} />}
  </article>;
}
