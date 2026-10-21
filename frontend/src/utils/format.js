const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const plain = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** 324.6 -> "$324.60" */
export const formatPrice = (n) => (n == null ? "—" : usd.format(n));

/** 7638.09 -> "7,638.09" (index values have no $) */
export const formatNumber = (n) => (n == null ? "—" : plain.format(n));

/** -0.98 -> "-0.98%",  1.2 -> "+1.20%" */
export const formatPercent = (n) =>
  n == null ? "—" : `${n > 0 ? "+" : ""}${plain.format(n)}%`;

/** -3.21 -> "-$3.21",  3.21 -> "+$3.21" */
export const formatChange = (n) =>
  n == null ? "—" : `${n > 0 ? "+" : n < 0 ? "-" : ""}${usd.format(Math.abs(n))}`;

/** 4.82e12 -> "$4.82T" */
export const formatMoneyCompact = (n) => (n == null ? "—" : `$${formatCompact(n)}`);

/** 54_200_000 -> "54.2M" */
export const formatCompact = (n) => {
  if (n == null) return "—";
  const units = [
    [1e12, "T"],
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "K"],
  ];
  for (const [size, label] of units) {
    if (Math.abs(n) >= size) return `${+(n / size).toFixed(2)}${label}`;
  }
  return String(n);
};

/** Alert timestamps: "Today 11:24 AM", "Yesterday 2:11 PM", "Oct 18, 9:30 AM" */
export const formatAlertTime = (iso) => {
  const d = new Date(iso);
  const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const dayDiff = Math.floor((startOfToday - d) / 86400e3) + 1; // 0 = today
  if (d >= startOfToday) return `Today ${time}`;
  if (dayDiff === 1) return `Yesterday ${time}`;
  return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })}, ${time}`;
};

/** "up" | "down" | "flat" - used to pick green/red styling */
export const direction = (n) => (n > 0 ? "up" : n < 0 ? "down" : "flat");