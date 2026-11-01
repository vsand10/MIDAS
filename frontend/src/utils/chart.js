/** Helpers for the price chart and the price/change header above it. */

export function formatTime(iso, range) {
  const d = new Date(iso);
  if (range === "1D") return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  if (range === "1W")
    return d.toLocaleString("en-US", { weekday: "short", hour: "numeric" });
  if (range === "1Y")
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const RANGE_LABEL = {
  "1D": "Today",
  "1W": "Past week",
  "1M": "Past month",
  "3M": "Past 3 months",
  "1Y": "Past year",
};

/**
 * Works out what the big price + change line should show:
 *  - while dragging on the chart: the touched point, vs. the start of the range
 *  - "1D": today's change from the quote
 *  - other ranges: change across the chart's range
 */
export function getPriceDisplay({ value, change, changePercent }, history, range, scrubPoint) {
  const start = history?.[0]?.price;
  if (scrubPoint && start) {
    const diff = scrubPoint.price - start;
    return {
      value: scrubPoint.price,
      change: diff,
      changePercent: (diff / start) * 100,
      label: formatTime(scrubPoint.time, range),
    };
  }
  if (range !== "1D" && start) {
    const diff = value - start;
    return { value, change: diff, changePercent: (diff / start) * 100, label: RANGE_LABEL[range] };
  }
  return { value, change, changePercent, label: RANGE_LABEL["1D"] };
}