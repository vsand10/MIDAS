import { Link } from "react-router-dom";
import { direction, formatPercent, formatPrice } from "../../utils/format";
import "./StockRow.css";

/** One stock in a list: symbol + name on the left, price + % change on the right. */
export default function StockRow({ stock, onSelect }) {
  const { symbol, name, price, changePercent } = stock;
  return (
    <Link to={`/stock/${symbol}`} className="stock-row" onClick={() => onSelect?.(symbol)}>
      <div className="stock-row__left">
        <span className="stock-row__symbol">{symbol}</span>
        <span className="stock-row__name">{name}</span>
      </div>
      <div className="stock-row__right">
        <span className="stock-row__price">{formatPrice(price)}</span>
        <ChangeBadge value={changePercent} />
      </div>
    </Link>
  );
}

/** Green/red pill with the % change */
export function ChangeBadge({ value }) {
  return (
    <span className={`change-badge change-badge--${direction(value)}`}>
      {formatPercent(value)}
    </span>
  );
}

/** Grey placeholder rows while data loads */
export function StockRowSkeleton({ count = 3 }) {
  return Array.from({ length: count }, (_, i) => (
    <div className="stock-row stock-row--skeleton" key={i} aria-hidden="true">
      <div className="stock-row__left">
        <span className="skeleton" style={{ width: 52, height: 14 }} />
        <span className="skeleton" style={{ width: 96, height: 11, marginTop: 6 }} />
      </div>
      <div className="stock-row__right">
        <span className="skeleton" style={{ width: 64, height: 14 }} />
        <span className="skeleton" style={{ width: 56, height: 18, marginTop: 4 }} />
      </div>
    </div>
  ));
}