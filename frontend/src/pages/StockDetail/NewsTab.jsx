import { useAsync } from "../../hooks/useAsync";
import { getNews } from "../../services/stockservice";
import { formatRelativeTime } from "../../utils/format";
import "./NewsTab.css";

/**
 * "News" tab on the Stock Detail screen.
 * Shows loading, error (with Try again), empty and list states.
 * Tapping an article opens the full story in a new browser tab.
 */
export default function NewsTab({ symbol }) {
  const { data, loading, error, reload } = useAsync(() => getNews(symbol), [symbol]);

  let content;
  if (loading && !data) {
    content = <NewsSkeleton />;
  } else if (error) {
    content = (
      <div className="error-state" role="alert">
        Couldn&apos;t load news.
        <br />
        <button type="button" onClick={reload}>
          Try again
        </button>
      </div>
    );
  } else if (!data?.length) {
    content = <p className="empty-state">No recent news for this stock</p>;
  } else {
    content = (
      <ul className="news-list" aria-label="Recent news">
        {data.map((article) => (
          <li key={article.id}>
            <a
              className="news-item"
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              <span className="news-item__title">{article.title}</span>
              <span className="news-item__meta">
                {article.source} ·{" "}
                <time dateTime={article.publishedAt}>
                  {formatRelativeTime(article.publishedAt)}
                </time>
              </span>
            </a>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <section className="list-card news" aria-busy={loading}>
      {content}
    </section>
  );
}

/** Grey placeholder rows while the news loads */
function NewsSkeleton() {
  return Array.from({ length: 4 }, (_, i) => (
    <div className="news-item" key={i} aria-hidden="true">
      <span className="skeleton" style={{ width: "92%", height: 14 }} />
      <span className="skeleton" style={{ width: "60%", height: 14, marginTop: 6 }} />
      <span className="skeleton" style={{ width: 110, height: 11, marginTop: 8 }} />
    </div>
  ));
}
