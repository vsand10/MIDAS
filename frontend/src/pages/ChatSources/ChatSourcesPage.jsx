import { useLocation, useNavigate } from "react-router-dom";
import "../../App.css";
import "./ChatSourcesPage.css";

export default function ChatSourcesPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const sources = Array.isArray(location.state?.sources)
    ? location.state.sources
    : [];

  const question = location.state?.question || "";

  const goBack = () => {
    if (window.history.length > 1) navigate(-1);
    else navigate("/chat");
  };

  return (
    <div className="chat-sources">
      <header className="chat-sources__header">
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

        <h1 className="chat-sources__title">Sources</h1>
      </header>

      <main className="chat-sources__content">
        {question && (
          <div className="chat-sources__question">
            <span className="chat-sources__label">Question</span>
            <p>{question}</p>
          </div>
        )}

        {sources.length > 0 ? (
          <div className="chat-sources__list">
            {sources.map((source, index) => (
              <a
                key={`${source.url}-${index}`}
                className="chat-sources__item"
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="chat-sources__number">{index + 1}</span>

                <span className="chat-sources__info">
                  <span className="chat-sources__source-title">
                    {source.title || "Source"}
                  </span>
                  <span className="chat-sources__url">{source.url}</span>
                </span>

                <span className="chat-sources__arrow" aria-hidden="true">
                  ›
                </span>
              </a>
            ))}
          </div>
        ) : (
          <p className="chat-sources__empty">
            No sources are available for this answer.
          </p>
        )}
      </main>
    </div>
  );
}