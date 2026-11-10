import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useAsync } from "../../hooks/useAsync";
import { getStock } from "../../services/stockservice";
import "./WhyMovedPage.css";



export default function WhyMovedPage() {
  const { symbol } = useParams();
  const sym = symbol.toUpperCase();
  const navigate = useNavigate();
  const location = useLocation();

  // Only used for the company name in the titles; the page works without it
  const stock = useAsync(() => getStock(sym).catch(() => null), [sym]);
  const name = shortName(stock.data?.name || location.state?.name) || sym;

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

      {/* ---------- AI Summary (placeholder) ---------- */}
      <section className="why__summary" aria-labelledby="why-summary-title">
        <div className="why__summary-header">
          <h2 id="why-summary-title" className="why__summary-label">
            AI Summary
          </h2>
          <span className="why__badge">AI-generated</span>
        </div>
        {/* TODO (AI Summary): replace this paragraph with the generated summary for `sym` */}
        <p className="why__placeholder-text">
          The AI summary for {name} is coming soon.
        </p>
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

      {/* ---------- Key Drivers (placeholder) ---------- */}
      <section className="why__drivers" aria-labelledby="why-drivers-title">
        <h2 id="why-drivers-title" className="why__section-label">
          Key Drivers
        </h2>
        {/* TODO (Key Drivers): replace with one .why__driver card per driver:
              <article className="why__driver">
                <h3 className="why__driver-title">Product event anticipation</h3>
                <p className="why__driver-text">...</p>
              </article>
        */}
        <article className="why__driver why__driver--placeholder">
          <h3 className="why__driver-title">Key drivers are coming soon</h3>
          <p className="why__driver-text">
            The main reasons behind {name}&apos;s latest move will be listed here.
          </p>
        </article>
      </section>

      {/* ---------- Sources (placeholder) ---------- */}
      {/* TODO (Sources): show the real count ("5 sources") and open the Sources screen */}
      <button type="button" className="why__sources" disabled>
        Sources coming soon
      </button>
    </main>
  );
}

function shortName(name) {
  if (!name) return "";
  return name.replace(/,? (Inc\.?|Corp\.?|Corporation|Co\.|Ltd\.?|plc|Group|& Co\.)$/i, "");
}