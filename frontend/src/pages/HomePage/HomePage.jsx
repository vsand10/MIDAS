import { useState } from "react";
import { Link } from "react-router-dom";
import PriceChart from "../../components/PriceChart/PriceChart";
import PriceChange from "../../components/PriceChart/PriceChange";
import StockList from "../../components/Stocklist";
import { useAsync } from "../../hooks/useAsync";
import { getPriceDisplay } from "../../utils/chart";
import { getMarketIndex, getTopMovers, getWatchlist } from "../../services/stockservice";
import { formatNumber } from "../../utils/format";
import "./HomePage.css";

export default function HomePage() {
  const [range, setRange] = useState("1D");
  const [scrub, setScrub] = useState(null);

  const market = useAsync(() => getMarketIndex(range), [range]);
  const movers = useAsync(() => getTopMovers(4), []);
  const watchlist = useAsync(() => getWatchlist(), []);

  return (
    <main className="page home">
      <header className="home__header">
        <span className="home__brand">MIDAS</span>
      </header>

      {/* ---------- Market index card ---------- */}
      <section className="card home__market" aria-label="Market overview">
        <MarketHeader state={market} range={range} scrub={scrub} />
        {market.error ? (
          <div className="error-state" role="alert">
            Couldn&apos;t load the market chart.
            <br />
            <button type="button" onClick={market.reload}>
              Try again
            </button>
          </div>
        ) : (
          <PriceChart
            data={market.data?.history}
            loading={market.loading}
            range={range}
            onRangeChange={setRange}
            onScrub={setScrub}
            height={150}
          />
        )}
      </section>

      {/* ---------- Top movers ---------- */}
      <section className="section">
        <div className="section__header">
          <h2 className="section__title">Top Movers Today</h2>
        </div>
        <StockList state={movers} skeletonCount={4} emptyText="No big moves yet today." />
      </section>

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

function MarketHeader({ state, range, scrub }) {
  const { data } = state;
  if (!data) {
    return (
      <div className="home__market-header" aria-hidden="true">
        <span className="skeleton" style={{ width: 70, height: 13 }} />
        <span className="skeleton" style={{ width: 140, height: 26, marginTop: 8 }} />
        <span className="skeleton" style={{ width: 120, height: 13, marginTop: 8 }} />
      </div>
    );
  }
  const shown = getPriceDisplay(data, data.history, range, scrub);
  return (
    <div className="home__market-header">
      <h1 className="home__market-name">{data.name}</h1>
      <p className="home__market-value">{formatNumber(shown.value)}</p>
      <PriceChange {...shown} isIndex />
    </div>
  );
}