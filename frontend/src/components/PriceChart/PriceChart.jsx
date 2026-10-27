import { useId, useMemo, useState } from "react";
import { RANGES } from "../../services/stockservice";
import { formatTime } from "../../utils/chart";
import { formatNumber } from "../../utils/format";
import "./PriceChart.css";

const W = 340; // drawing units; the SVG scales to the card width
const PAD_Y = 10;

/**
 * Line chart + range tabs (1D / 1W / 1M / 3M / 1Y).
 *
 * Props:
 *  - data: [{ time, price }] oldest to newest (from getPriceHistory)
 *  - loading: show a placeholder while new data loads
 *  - range, onRangeChange(range): controlled range tabs
 *  - onScrub(point | null): called while the user drags across the chart
 *  - height: chart height in px
 */
export default function PriceChart({
  data,
  loading = false,
  range,
  onRangeChange,
  onScrub,
  height = 170,
}) {
  const gradientId = useId();
  const [active, setActive] = useState(null); // index being touched

  const chart = useMemo(() => buildChart(data, height), [data, height]);
  const trend = chart && chart.last >= chart.first ? "up" : "down";

  const handlePointer = (e) => {
    if (!chart) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.max(0, Math.min(data.length - 1, Math.round(x / chart.stepX)));
    setActive(i);
    onScrub?.(data[i]);
  };

  const clearPointer = () => {
    setActive(null);
    onScrub?.(null);
  };

  const point = active != null && chart ? chart.points[active] : null;

  return (
    <div className={`price-chart price-chart--${trend}`}>
      <div className="price-chart__plot" style={{ height }}>
        {loading || !chart ? (
          <div className="skeleton price-chart__loading" />
        ) : (
          <svg
            viewBox={`0 0 ${W} ${height}`}
            preserveAspectRatio="none"
            className="price-chart__svg"
            onPointerDown={handlePointer}
            onPointerMove={handlePointer}
            onPointerLeave={clearPointer}
            onPointerUp={(e) => e.pointerType !== "mouse" && clearPointer()}
            role="img"
            aria-label={`Price chart, ${range}: from ${formatNumber(chart.first)} to ${formatNumber(chart.last)}`}
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" className="price-chart__fill-start" />
                <stop offset="100%" className="price-chart__fill-end" />
              </linearGradient>
            </defs>

            {/* starting price reference line */}
            <line
              x1="0"
              x2={W}
              y1={chart.baselineY}
              y2={chart.baselineY}
              className="price-chart__baseline"
              vectorEffect="non-scaling-stroke"
            />
            <path d={chart.area} fill={`url(#${gradientId})`} />
            <path d={chart.line} className="price-chart__line" vectorEffect="non-scaling-stroke" />

            {point && (
              <line
                x1={point.x}
                x2={point.x}
                y1="0"
                y2={height}
                className="price-chart__cursor"
                vectorEffect="non-scaling-stroke"
              />
            )}
          </svg>
        )}

        {point && !loading && (
          <>
            <span
              className="price-chart__dot"
              style={{ left: `${(point.x / W) * 100}%`, top: point.y }}
            />
            <span
              className="price-chart__label"
              style={{ left: `clamp(40px, ${(point.x / W) * 100}%, calc(100% - 40px))` }}
            >
              {formatNumber(data[active].price)} · {formatTime(data[active].time, range)}
            </span>
          </>
        )}
      </div>

      {onRangeChange && (
        <div className="price-chart__ranges" role="tablist" aria-label="Chart range">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              role="tab"
              aria-selected={r === range}
              className={`price-chart__range${r === range ? " is-active" : ""}`}
              onClick={() => onRangeChange(r)}
            >
              {r}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function buildChart(data, height) {
  if (!data || data.length < 2) return null;
  const prices = data.map((d) => d.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const stepX = W / (data.length - 1);
  const y = (p) => PAD_Y + (1 - (p - min) / span) * (height - PAD_Y * 2);

  const points = prices.map((p, i) => ({ x: i * stepX, y: y(p) }));
  const line = points.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join("");
  const area = `${line}L${W},${height}L0,${height}Z`;

  return {
    points,
    line,
    area,
    stepX,
    first: prices[0],
    last: prices[prices.length - 1],
    baselineY: y(prices[0]),
  };
}