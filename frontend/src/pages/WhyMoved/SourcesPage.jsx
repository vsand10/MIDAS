import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useAsync } from "../../hooks/useAsync";
import { getWhyItMoved } from "../../services/stockservice";
import { sourceCount, sourceLine } from "./sourceFormat";
import "./WhyMovedPage.css";

/** The articles MIDAS used for the "Why did X move?" summary */
export default function SourcesPage() {
  const { symbol } = useParams();
  const sym = symbol.toUpperCase();
  const navigate = useNavigate();
  const location = useLocation();
  const name = location.state?.name || sym;

  // The server saved this result when the Why screen was opened, so this is not a new AI call
  const why = useAsync(() => getWhyItMoved(sym), [sym]);
  const sources = why.data?.status === "ok" ? why.data.sources : [];

  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate(`/stock/${sym}/why`));

  return (
    <main className="page why">
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

      <h1 className="page-title why__title">Sources for {name}</h1>
      {sources.length > 0 && <p className="why__source-count">{sourceCount(sources.length)} used</p>}

      {why.loading && !why.data ? (
        <p className="why__placeholder-text" aria-busy="true">
          Loading sources…
        </p>
      ) : why.error ? (
        <div role="alert">
          <p className="why__placeholder-text">
            {why.error.message || "Couldn't load the sources."}
          </p>
          <button type="button" className="why__retry" onClick={why.reload}>
            Try again
          </button>
        </div>
      ) : sources.length === 0 ? (
        <p className="why__placeholder-text">
          {why.data.message || "Not enough information to explain this move"}
        </p>
      ) : (
        <ul className="why__source-list">
          {sources.map((src) => (
            <li key={src.url}>
              <a className="why__source" href={src.url} target="_blank" rel="noreferrer">
                <span className="why__source-meta">{sourceLine(src)}</span>
                <span className="why__source-title">{src.title}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
