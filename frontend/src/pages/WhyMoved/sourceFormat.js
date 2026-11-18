// Small text helpers for the Why-it-moved screens (kept here so they can be tested)

/** "Nov 9, 2026", or "" if the date is missing or invalid */
export function formatSourceDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** "Reuters · Nov 9, 2026" (leaves out whatever is missing) */
export function sourceLine(src) {
  return [src?.source, formatSourceDate(src?.publishedAt)].filter(Boolean).join(" · ");
}

/** "1 source" / "5 sources" */
export function sourceCount(count) {
  return `${count} ${count === 1 ? "source" : "sources"}`;
}

/** "+1.20%", "-0.15%", "0.00%" */
export function formatChange(percent) {
  if (typeof percent !== "number" || Number.isNaN(percent)) return "";
  const sign = percent > 0 ? "+" : "";
  return `${sign}${percent.toFixed(2)}%`;
}

/** The "how did the market do" chips: indexes first, then the stock's sector */
export function comparisonItems(comparison) {
  if (!comparison) return [];
  const items = (comparison.indexes || []).map((i) => ({
    label: i.name,
    change: i.changePercent,
  }));
  if (comparison.sector) {
    items.push({ label: `${comparison.sector.name} sector`, change: comparison.sector.changePercent });
  }
  return items;
}
