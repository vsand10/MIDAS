import { useEffect, useState } from "react";
import StockList from "../../components/Stocklist";
import { useAsync } from "../../hooks/useAsync";
import {
  SECTORS,
  addRecentSearch,
  clearRecentSearches,
  getRecentSearches,
  getTrendingThemes,
  searchStocks,
} from "../../services/stockservice";

import "./SearchPage.css";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("All");
  const debouncedQuery = useDebounced(query.trim(), 250);
  const isBrowsing = !debouncedQuery && sector === "All";

  const results = useAsync(
    () => (isBrowsing ? Promise.resolve([]) : searchStocks(debouncedQuery, sector)),
    [debouncedQuery, sector]
  );
  const recent = useAsync(() => getRecentSearches(5), []);
  const trending = useAsync(() => getTrendingThemes(), []);

  const onSelect = (symbol) => addRecentSearch(symbol);

  const clearRecent = () => {
    clearRecentSearches();
    recent.reload();
  };

  return (
    <main className="page search">
      <h1 className="page-title">Find a Stock</h1>

      <form className="search__bar" role="search" onSubmit={(e) => e.preventDefault()}>
        <label htmlFor="stock-search" className="visually-hidden">
          Search stocks
        </label>
        <svg className="search__icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M16 16l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <input
          id="stock-search"
          type="search"
          className="search__input"
          placeholder="Search company or ticker"
          autoComplete="off"
          autoCapitalize="characters"
          enterKeyHint="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query && (
          <button
            type="button"
            className="search__clear"
            onClick={() => setQuery("")}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </form>

      <div className="search__chips" role="group" aria-label="Filter by sector">
        {SECTORS.map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={s === sector}
            className={`search__chip${s === sector ? " is-active" : ""}`}
            onClick={() => setSector(s)}
          >
            {s}
          </button>
        ))}
      </div>

      {isBrowsing ? (
        <>
          {/* ---------- Recent searches ---------- */}
          {recent.data?.length > 0 && (
            <section className="section">
              <div className="section__header">
                <h2 className="section__title">Recent Searches</h2>
                <button type="button" className="section__link" onClick={clearRecent}>
                  Clear
                </button>
              </div>
              <StockList state={recent} onSelect={onSelect} />
            </section>
          )}

          {/* ---------- Trending ---------- */}
          <section className="section">
            <div className="section__header">
              <h2 className="section__title">Trending Now</h2>
            </div>
            {trending.loading && !trending.data ? (
              <StockList state={trending} />
            ) : trending.error ? (
              <StockList state={trending} />
            ) : (
              trending.data.map((t) => (
                <div className="search__theme" key={t.theme}>
                  <h3 className="search__theme-name">{t.theme}</h3>
                  <p className="search__theme-desc">{t.description}</p>
                  <StockList state={{ data: t.stocks }} onSelect={onSelect} />
                </div>
              ))
            )}
          </section>
        </>
      ) : (
        /* ---------- Results ---------- */
        <section className="section" aria-live="polite">
          <div className="section__header">
            <h2 className="section__title">
              {debouncedQuery ? `Results for “${debouncedQuery}”` : `${sector} stocks`}
            </h2>
          </div>
          <StockList
            state={results}
            onSelect={onSelect}
            skeletonCount={4}
            emptyText="No stocks match your search."
          />
        </section>
      )}
    </main>
  );
}

function useDebounced(value, delay) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}