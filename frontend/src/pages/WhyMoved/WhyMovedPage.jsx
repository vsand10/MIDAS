import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useAsync } from "../../hooks/useAsync";
import { getStock, getWhyItMoved } from "../../services/stockservice";
import { comparisonItems, formatChange, sourceCount, sourceLine } from "./sourceFormat";
import "./WhyMovedPage.css";



export default function WhyMovedPage() {
  const { symbol } = useParams();
  const sym = symbol.toUpperCase();
  const navigate = useNavigate();
  const location = useLocation();

  // Only used for the company name in the titles; the page works without it
  const stock = useAsync(() => getStock(sym).catch(() => null), [sym]);
  const name = shortName(stock.data?.name || location.state?.name) || sym;

   // One request fills the summary, key drivers and sources (the server saves it for 30 minutes)
  const why = useAsync(() => getWhyItMoved(sym), [sym]);
  const result = why.data;
  const ok = result?.status === "ok";
  const compare = ok ? comparisonItems(result.comparison) : [];

  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate(`/stock/${sym}`));

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

      <h1 className="page-title why__title">Why did {name} move?</h1>

      {/* ---------- AI Summary ---------- */}
      <section className="why__summary" aria-labelledby="why-summary-title">
        <div className="why__summary-header">
          <h2 id="why-summary-title" className="why__summary-label">
            AI Summary
          </h2>
          <span className="why__badges">
            <span className="why__badge">AI-generated</span>
            {ok && result.origin === "web" && (
              <span className="why__badge why__badge--web">Web search</span>
            )}
          </span>
        </div>
        {why.loading && !result ? (
          <p className="why__placeholder-text" aria-busy="true">
            Writing the summary for {name}…
          </p>
        ) : why.error ? (
          <div role="alert">
            <p className="why__placeholder-text">
              {why.error.message || "Couldn't load the explanation."}
            </p>
            <button type="button" className="why__retry" onClick={why.reload}>
              Try again
            </button>
          </div>
        ) : ok ? (
          <>
            <p className="why__summary-text">{result.summary}</p>
            {compare.length > 0 && (
              <div className="why__compare" aria-label="How the market moved today">
                <span className="why__compare-label">
                  {sym} {formatChange(result.changePercent)} vs
                </span>
                <ul className="why__compare-list">
                  {compare.map((c) => (
                    <li
                      key={c.label}
                      className={`why__chip ${c.change >= 0 ? "why__chip--up" : "why__chip--down"}`}
                    >
                      {c.label} {formatChange(c.change)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : (
          <p className="why__placeholder-text">
            {result.message || "Not enough information to explain this move"}
          </p>
        )}
      </section>

      {/* ---------- Chat with AI ---------- */}
      <Link to={`/stock/${sym}/chat`} state={{ name }} className="why__chat-link">
        <span className="why__chat-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="26" height="26">
            <path
              d="M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5h-6.2L8.5 20v-3.5H5A1.5 1.5 0 0 1 3.5 15V7A1.5 1.5 0 0 1 5 5.5z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinejoin="round"
            />
            <path
              d="M8 9.5h8M8 12.5h5"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
            />
          </svg>
        </span>
        <span className="why__chat-text">
          <span className="why__chat-title">Chat with AI</span>
          <span className="why__chat-subtitle">Ask follow up questions about {name}</span>
        </span>
        <svg className="why__chat-chevron" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
          <path
            d="M9 5l7 7-7 7"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </Link>

      {/* ---------- Key Drivers ---------- */}
      <section className="why__drivers" aria-labelledby="why-drivers-title">
        <h2 id="why-drivers-title" className="why__section-label">
          Key Drivers
        </h2>
        {why.loading && !result ? (
          <article className="why__driver why__driver--placeholder" aria-busy="true">
            <p className="why__driver-text">Looking for the main drivers…</p>
          </article>
        ) : why.error ? null : ok && result.drivers.length > 0 ? (
          result.drivers.map((d, i) => (
            <a
              key={`${i}-${d.title}`}
              className="why__driver why__driver--link"
              href={d.source.url}
              target="_blank"
              rel="noreferrer"
            >
              <h3 className="why__driver-title">{d.title}</h3>
              <p className="why__driver-text">{d.description}</p>
              <span className="why__driver-source">
                {d.source.title} · {sourceLine(d.source)}
              </span>
            </a>
          ))
        ) : (
          <article className="why__driver why__driver--placeholder">
            <h3 className="why__driver-title">
              {(ok && result.driversMessage) || "No key drivers identified"}
            </h3>
          </article>
        )}
      </section>

      {/* ---------- Sources ---------- */}
      {ok && result.sources.length > 0 && (
        <Link to={`/stock/${sym}/why/sources`} state={{ name }} className="why__sources">
          {sourceCount(result.sources.length)}
        </Link>
      )}
    </main>
  );
}

function shortName(name) {
  if (!name) return "";
  return name.replace(/,? (Inc\.?|Corp\.?|Corporation|Co\.|Ltd\.?|plc|Group|& Co\.)$/i, "");
}