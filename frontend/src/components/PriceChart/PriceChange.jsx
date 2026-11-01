import { direction, formatChange, formatNumber, formatPercent } from "../../utils/format";
import "./PriceChart.css";

/** "▼ -$3.21 (-0.98%) Today" in green/red. Set isIndex for points instead of dollars. */
export default function PriceChange({ change, changePercent, label, isIndex = false }) {
  const dir = direction(change);
  const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "";
  const amount = isIndex
    ? `${change > 0 ? "+" : ""}${formatNumber(change)}`
    : formatChange(change);
  return (
    <p className={`price-change is-${dir}`}>
      <span aria-hidden="true">{arrow} </span>
      {amount} ({formatPercent(changePercent)})
      <span className="price-change__label"> {label}</span>
    </p>
  );
}