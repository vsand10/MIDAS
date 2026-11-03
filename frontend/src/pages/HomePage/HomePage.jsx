import { useState } from "react";
import { Link } from "react-router-dom";
import PriceChart from "../../components/PriceChart/PriceChart";
import PriceChange from "../../components/PriceChart/PriceChange";
import { ChangeBadge } from "../../components/StockRow/StockRow";
import StockList from "../../components/Stocklist";
import { REFRESH_EVERY_MS, useAsync } from "../../hooks/useAsync";
import { getPriceDisplay } from "../../utils/chart";
import {
  getIndexHistory,
  getMarketOverview,
  getTopMovers,
  getWatchlist,
} from "../../services/stockservice";
import { formatNumber } from "../../utils/format";
import "./HomePage.css";

export default function HomePage() {
  const [range, setRange] = useState("1D");
  const [selected, setSelected] = useState("^GSPC"); // which index the chart shows
  const [scrub, setScrub] = useState(null);

  // Everything on Home refreshes quietly once a minute (see useAsync)
  const live = { refreshMs: REFRESH_EVERY_MS };
  const overview = useAsync(() => getMarketOverview(), [], live);
  const movers = useAsync(() => getTopMovers(4), [], live);
  const history = useAsync(() => getIndexHistory(selected, range), [selected, range], live);
  const watchlist = useAsync(() => getWatchlist(), [], live);

  // If the market data API fails, one message + Retry replaces the market sections
  const marketFailed = Boolean(overview.error || movers.error);
  const retryMarket = () => {
    overview.reload();
    movers.reload();
    history.reload();
  };

  const index = overview.data?.find((i) => i.symbol === selected);

  return (
    <main className="page home">
      <header className="home__header">
        <span className="home__brand">MIDAS</span>
      </header>

      {marketFailed ? (
        <section className="card home__market" aria-label="Market overview">
          <div className="error-state" role="alert">
            Market data is unavailable right now
            <br />
            <button type="button" onClick={retryMarket}>
              Retry
            </button>
          </div>
        </section>
      ) : (
        <>
          {/* ---------- Market overview: three indices + chart ---------- */}
          <section className="card home__market" aria-label="Market overview">
            <IndexTabs
              indices={overview.data}
              selected={selected}
              onSelect={(symbol) => {
                setSelected(symbol);
                setScrub(null);
              }}
            />
            <MarketHeader index={index} history={history.data} range={range} scrub={scrub} />
            {history.error ? (
              <div className="error-state" role="alert">
                Couldn&apos;t load the market chart.
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
                height={150}
              />
            )}
            <p className="home__note">
              Live index levels are estimated from the SPY, ONEQ and DIA funds that track them.
            </p>
          </section>

          {/* ---------- Top movers ---------- */}
          <section className="section">
            <div className="section__header">
              <h2 className="section__title">Top Movers Today</h2>
            </div>
            <h3 className="home__subtitle">Top Gainers</h3>
            <StockList
              state={{ ...movers, data: movers.data?.gainers }}
              skeletonCount={4}
              emptyText="No gainers yet today."
            />
            <h3 className="home__subtitle">Top Losers</h3>
            <StockList
              state={{ ...movers, data: movers.data?.losers }}
              skeletonCount={4}
              emptyText="No losers yet today."
            />
          </section>
        </>
      )}

      {/* ---------- Watchlist ---------- */}
      <section className="section">
        <div className="section__header">
          <h2 className="section__title">My Watchlist</h2>
          <Link to="/watchlist" className="section__link">
            See All
          </Link>
        </div>
        <StockList
          state={watchlist}
          limit={5}
          emptyText="Your watchlist is empty. Search for a stock and tap “Add to Watchlist”."
        />
      </section>
    </main>
  );
}

/** S&P 500 / Nasdaq / Dow, each with value and percent change. Tap one to chart it. */
function IndexTabs({ indices, selected, onSelect }) {
  if (!indices) {
    return (
      <div className="home__indices" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span key={i} className="skeleton" style={{ height: 66, borderRadius: 12 }} />
        ))}
      </div>
    );
  }
  return (
    <div className="home__indices">
      {indices.map((i) => (
        <button
          key={i.symbol}
          type="button"
          className={`home__index${i.symbol === selected ? " is-active" : ""}`}
          aria-pressed={i.symbol === selected}
          onClick={() => onSelect(i.symbol)}
        >
          <span className="home__index-name">{i.name}</span>
          <span className="home__index-value">{formatNumber(i.value)}</span>
          <ChangeBadge value={i.changePercent} />
        </button>
      ))}
    </div>
  );
}

function MarketHeader({ index, history, range, scrub }) {
  if (!index) {
    return (
      <div className="home__market-header" aria-hidden="true">
        <span className="skeleton" style={{ width: 70, height: 13 }} />
        <span className="skeleton" style={{ width: 140, height: 26, marginTop: 8 }} />
        <span className="skeleton" style={{ width: 120, height: 13, marginTop: 8 }} />
      </div>
    );
  }
  const shown = getPriceDisplay(index, history, range, scrub);
  return (
    <div className="home__market-header">
      <h1 className="home__market-name">{index.name}</h1>
      <p className="home__market-value">{formatNumber(shown.value)}</p>
      <PriceChange {...shown} isIndex />
    </div>
  );
}
