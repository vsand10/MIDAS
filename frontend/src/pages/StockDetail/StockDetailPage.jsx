import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ConfirmModal from "../../components/Modal/ConfirmModal";
import PriceChart from "../../components/PriceChart/PriceChart";
import PriceChange from "../../components/PriceChart/PriceChange";
import { ChangeBadge } from "../../components/StockRow/StockRow";
import { useAsync } from "../../hooks/useAsync";
import { getPriceDisplay } from "../../utils/chart";
import {
  NotFoundError,
  addToWatchlist,
  getPriceHistory,
  getStock,
  isInWatchlist,
  removeFromWatchlist,
} from "../../services/stockservice";

import { formatCompact, formatMoneyCompact, formatPrice } from "../../utils/format";
import "./StockDetailPage.css";

const TABS = ["Overview", "Why it moved", "News", "Sentiment"];

export default function StockDetailPage() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const [range, setRange] = useState("1D");
  const [scrub, setScrub] = useState(null);
  const [tab, setTab] = useState("Overview");

  const stock = useAsync(() => getStock(symbol), [symbol]);
  const history = useAsync(() => getPriceHistory(symbol, range), [symbol, range]);

  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate("/home"));

  if (stock.error instanceof NotFoundError) {
    return (
      <main className="page">
        <BackButton onClick={goBack} />
        <div className="stock__not-found">
          <h1>Stock not found</h1>
          <p>We couldn&apos;t find a stock with the symbol “{symbol.toUpperCase()}”.</p>
          <button type="button" className="btn btn--primary" onClick={() => navigate("/search")}>
            Search stocks
          </button>
        </div>
      </main>
    );
  }

  if (stock.error) {
    return (
      <main className="page">
        <BackButton onClick={goBack} />
        <div className="error-state" role="alert">
          Couldn&apos;t load this stock.
          <br />
          <button type="button" onClick={stock.reload}>
            Try again
          </button>
        </div>
      </main>
    );
  }

  const data = stock.data;
  const shown = data
    ? getPriceDisplay({ ...data, value: data.price }, history.data, range, scrub)
    : null;

  return (
    <main className="page stock">
      <BackButton onClick={goBack} />

      {/* ---------- Price header ---------- */}
      {data ? (
        <header className="stock__header">
          <h1 className="stock__name">{data.name}</h1>
          <p className="stock__meta">
            {data.symbol} · {data.sector}
          </p>
          <p className="stock__price">{formatPrice(shown.value)}</p>
          <PriceChange {...shown} />
        </header>
      ) : (
        <header className="stock__header" aria-hidden="true">
          <span className="skeleton" style={{ width: 150, height: 22 }} />
          <span className="skeleton" style={{ width: 90, height: 13, marginTop: 8 }} />
          <span className="skeleton" style={{ width: 130, height: 30, marginTop: 12 }} />
          <span className="skeleton" style={{ width: 160, height: 14, marginTop: 8 }} />
        </header>
      )}

      {/* ---------- Chart ---------- */}
      <section className="stock__chart" aria-label="Price chart">
        {history.error ? (
          <div className="error-state" role="alert">
            Couldn&apos;t load the chart.
            <br />
            <button type="button" onClick={history.reload}>
              Try again
            </button>
          </div>
        ) : (
          <PriceChart
            data={history.data}
            loading={history.loading}
            range={range}
            onRangeChange={setRange}
            onScrub={setScrub}
          />
        )}
      </section>

      {/* ---------- Tabs ---------- */}
      <div className="stock__tabs" role="tablist" aria-label="Stock details">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            id={`tab-${slug(t)}`}
            aria-selected={t === tab}
            aria-controls={`panel-${slug(t)}`}
            className={`stock__tab${t === tab ? " is-active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${slug(tab)}`} aria-labelledby={`tab-${slug(tab)}`}>
        {tab === "Overview" ? (
          <Overview stock={data} />
        ) : (
          <div className="card stock__coming-soon">
            {/* TODO: build the "{tab}" section once its API is ready */}
            <p>{tab} is coming soon.</p>
          </div>
        )}
      </div>

      {data && <WatchlistButton stock={data} />}
    </main>
  );
}

function Overview({ stock }) {
  if (!stock) {
    return <div className="skeleton" style={{ height: 230, borderRadius: 14 }} />;
  }
  const s = stock.stats;
  const rows = [
    ["Market Cap", formatMoneyCompact(s.marketCap)],
    ["Price-to-Earnings Ratio", s.peRatio?.toFixed(1) ?? "—"],
    ["52-Week Range", `${formatPrice(s.week52Low)} – ${formatPrice(s.week52High)}`],
    ["Avg. Volume", formatCompact(s.avgVolume)],
    ["Earnings per Share", formatPrice(s.eps)],
    ["Dividend Yield", s.dividendYield == null ? "None" : `${s.dividendYield.toFixed(2)}%`],
  ];

  return (
    <>
      <section className="section stock__section">
        <h2 className="section__title">Key Stats</h2>
        <dl className="card stock__stats">
          {rows.map(([label, value]) => (
            <div className="stock__stat" key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="section stock__section">
        <h2 className="section__title">About {stock.name}</h2>
        <p className="stock__about">{stock.about}</p>
      </section>
    </>
  );
}

function WatchlistButton({ stock }) {
  const saved = useAsync(() => isInWatchlist(stock.symbol), [stock.symbol]);
  const [inList, setInList] = useState(null); // local override after add/remove
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const isSaved = inList ?? saved.data;

  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      if (isSaved) await removeFromWatchlist(stock.symbol);
      else await addToWatchlist(stock.symbol);
      setInList(!isSaved);
      setConfirming(false);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="stock__watch">
        <button
          type="button"
          className={`btn ${isSaved ? "btn--ghost" : "btn--outline"} stock__watch-btn`}
          disabled={saved.loading}
          onClick={() => setConfirming(true)}
        >
          {isSaved ? "✓ In Watchlist" : "+ Add to Watchlist"}
        </button>
        {error && (
          <p className="stock__watch-error" role="alert">
            {error}
          </p>
        )}
      </div>

      <ConfirmModal
        open={confirming}
        title={isSaved ? "Remove from Watchlist?" : "Add to Watchlist?"}
        confirmLabel={isSaved ? "Remove" : "Add"}
        confirmVariant={isSaved ? "danger" : "primary"}
        busy={busy}
        onConfirm={confirm}
        onCancel={() => setConfirming(false)}
      >
        <div className="stock__modal-card">
          <span className="stock__logo" aria-hidden="true">
            {stock.symbol.slice(0, 4)}
          </span>
          <span className="stock__modal-name">
            <strong>{stock.name}</strong>
            <span>{stock.symbol}</span>
          </span>
          <span className="stock__modal-price">
            <strong>{formatPrice(stock.price)}</strong>
            <ChangeBadge value={stock.changePercent} />
          </span>
        </div>
      </ConfirmModal>
    </>
  );
}

function BackButton({ onClick }) {
  return (
    <button type="button" className="back-btn" onClick={onClick}>
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
        <path
          d="M15 5l-7 7 7 7"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      Back
    </button>
  );
}

const slug = (s) => s.toLowerCase().replace(/\s+/g, "-");