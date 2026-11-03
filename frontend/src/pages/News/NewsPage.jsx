import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import NewsCard, { NewsCardSkeleton } from "../../components/NewsCard/NewsCard";
import { useAsync } from "../../hooks/useAsync";
import { getNews, getStock } from "../../services/stockservice";
import { filterArticles } from "../../utils/news";
import "./NewsPage.css";

/** Full news list for one stock: /stock/:symbol/news */
export default function NewsPage() {
  const { symbol } = useParams();
  const sym = symbol.toUpperCase();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const news = useAsync(() => getNews(sym, 30), [sym]);
  // Only used for the title and the ticker pill; the page still works without it
  const stock = useAsync(() => getStock(sym).catch(() => null), [sym]);

  const articles = useMemo(() => filterArticles(news.data, query), [news.data, query]);

  const name = stock.data ? shortName(stock.data.name) : sym;
  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate(`/stock/${sym}`));

  return (
    <main className="page news">
      <button type="button" className="back-btn" onClick={goBack}>
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

      <h1 className="page-title news__title">{name} News</h1>

      <form className="news__search" role="search" onSubmit={(e) => e.preventDefault()}>
        <label htmlFor="news-search" className="visually-hidden">
          Search news
        </label>
        <svg className="news__search-icon" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M16 16l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <input
          id="news-search"
          type="search"
          className="news__search-input"
          placeholder="Search news..."
          autoComplete="off"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </form>

      <section className="section" aria-live="polite">
        <div className="section__header">
          <h2 className="section__title">Recent Events</h2>
        </div>

        {news.loading && !news.data ? (
          <div className="news__list">
            <NewsCardSkeleton count={4} />
          </div>
        ) : news.error ? (
          <div className="card error-state" role="alert">
            {news.error.message || "Couldn't load the news."}
            <br />
            <button type="button" onClick={news.reload}>
              Try again
            </button>
          </div>
        ) : articles.length === 0 ? (
          <p className="card empty-state">
            {query ? "No articles found" : "No recent news for this stock"}
          </p>
        ) : (
          <div className="news__list">
            {articles.map((a) => (
              <NewsCard
                key={a.id}
                article={a}
                symbol={sym}
                changePercent={stock.data?.changePercent}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

/** "Apple Inc." -> "Apple" for the page title */
function shortName(name) {
  return name.replace(/,? (Inc\.?|Corp\.?|Corporation|Co\.|Ltd\.?|plc|Group|& Co\.)$/i, "");
}