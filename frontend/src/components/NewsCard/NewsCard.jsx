import { describeSentiment, formatTimeAgo } from "../../utils/format";
import { ChangeBadge } from "../StockRow/StockRow";
import "./NewsCard.css";

/**
 * One news article. Tapping opens the full article in a new tab.
 *
 * Props:
 *  - article: NewsArticle (see getNews in stockService.js)
 *  - symbol, changePercent: optional ticker pill, e.g. "AAPL -0.98%"
 *  - compact: hide the summary (used in the stock page's News tab)
 */
export default function NewsCard({ article, symbol, changePercent, compact = false }) {
  const sentiment = describeSentiment(article.sentiment?.label);

  return (
    <a
      className="news-card"
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
    >
      <div className="news-card__body">
        <p className="news-card__meta">
          <span className="news-card__source">{article.source}</span>
          {article.publishedAt && <span> · {formatTimeAgo(article.publishedAt)}</span>}
        </p>
        <h3 className="news-card__title">{article.title}</h3>
        {!compact && article.summary && <p className="news-card__summary">{article.summary}</p>}

        {(symbol || sentiment) && (
          <div className="news-card__tags">
            {symbol && (
              <span className="news-card__ticker">
                {symbol}
                {changePercent != null && <ChangeBadge value={changePercent} />}
              </span>
            )}
            {sentiment && (
              <span className={`news-card__sentiment is-${sentiment.tone}`}>{sentiment.text}</span>
            )}
          </div>
        )}
      </div>

      {article.imageUrl && (
        <img className="news-card__image" src={article.imageUrl} alt="" loading="lazy" />
      )}
      <span className="visually-hidden"> (opens in a new tab)</span>
    </a>
  );
}

/** Grey placeholder cards while news loads */
export function NewsCardSkeleton({ count = 3 }) {
  return Array.from({ length: count }, (_, i) => (
    <div className="news-card news-card--skeleton" key={i} aria-hidden="true">
      <div className="news-card__body">
        <span className="skeleton" style={{ width: 120, height: 12 }} />
        <span className="skeleton" style={{ width: "95%", height: 15, marginTop: 10 }} />
        <span className="skeleton" style={{ width: "70%", height: 15, marginTop: 6 }} />
        <span className="skeleton" style={{ width: 110, height: 20, marginTop: 12 }} />
      </div>
    </div>
  ));
}