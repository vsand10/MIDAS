import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import ConfirmModal from "../../components/Modal/ConfirmModal";
import StockList from "../../components/Stocklist";
import { ChangeBadge } from "../../components/StockRow/StockRow";
import { useAsync } from "../../hooks/useAsync";
import { getAlerts, getWatchlist, removeFromWatchlist } from "../../services/stockservice";
import { formatAlertTime } from "../../utils/format";
import "./WatchlistPage.css";

export default function WatchlistPage() {
  const navigate = useNavigate();
  const watchlist = useAsync(() => getWatchlist(), []);
  const alerts = useAsync(() => getAlerts(5), []);
  const [editing, setEditing] = useState(false);

  const hasStocks = watchlist.data?.length > 0;

  return (
    <main className="page watchlist">
      <header className="watchlist__header">
        <h1 className="page-title watchlist__title">My Watchlist</h1>
        <div className="watchlist__actions">
          {hasStocks && (
            <button
              type="button"
              className="section__link"
              onClick={() => setEditing((e) => !e)}
            >
              {editing ? "Done" : "Edit"}
            </button>
          )}
          <button type="button" className="watchlist__add" onClick={() => navigate("/search")}>
            + Add
          </button>
        </div>
      </header>

      {/* ---------- Saved stocks ---------- */}
      {editing && hasStocks ? (
        <EditableList stocks={watchlist.data} onRemoved={watchlist.reload} />
      ) : watchlist.data && !hasStocks ? (
        <div className="card watchlist__empty">
          <p className="watchlist__empty-title">Your watchlist is empty</p>
          <p>Add stocks to follow their prices and get alerts when they move.</p>
          <Link to="/search" className="btn btn--primary watchlist__empty-btn">
            Find a Stock
          </Link>
        </div>
      ) : (
        <StockList state={watchlist} skeletonCount={5} />
      )}

      {/* ---------- Alerts ---------- */}
      <section className="section">
        <div className="section__header">
          <h2 className="section__title">Recent Alerts</h2>
        </div>
        <AlertList state={alerts} />
      </section>
    </main>
  );
}

/** Watchlist in edit mode: each row gets a remove button */
function EditableList({ stocks, onRemoved }) {
  const [pending, setPending] = useState(null); // stock waiting for confirmation
  const [removed, setRemoved] = useState([]); // hide removed rows right away
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const confirmRemove = async () => {
    setBusy(true);
    setError("");
    try {
      await removeFromWatchlist(pending.symbol);
      setRemoved((r) => [...r, pending.symbol]);
      setPending(null);
      onRemoved();
    } catch {
      setError("Couldn't remove that stock. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="list-card">
        {stocks.filter((s) => !removed.includes(s.symbol)).map((s) => (
          <div className="stock-row watchlist__edit-row" key={s.symbol}>
            <div className="stock-row__left">
              <span className="stock-row__symbol">{s.symbol}</span>
              <span className="stock-row__name">{s.name}</span>
            </div>
            <button
              type="button"
              className="watchlist__remove"
              onClick={() => setPending(s)}
              aria-label={`Remove ${s.symbol} from watchlist`}
            >
              Remove
            </button>
          </div>
        ))}
      </div>
      {error && (
        <p className="watchlist__error" role="alert">
          {error}
        </p>
      )}

      <ConfirmModal
        open={!!pending}
        title="Remove from Watchlist?"
        confirmLabel="Remove"
        confirmVariant="danger"
        busy={busy}
        onConfirm={confirmRemove}
        onCancel={() => setPending(null)}
      >
        {pending && (
          <div className="watchlist__modal-stock">
            <strong>{pending.symbol}</strong>
            <span>{pending.name}</span>
            <ChangeBadge value={pending.changePercent} />
          </div>
        )}
      </ConfirmModal>
    </>
  );
}

function AlertList({ state }) {
  const { data, loading, error, reload } = state;

  if (loading && !data) {
    return (
      <div className="watchlist__alerts" aria-hidden="true">
        {[0, 1].map((i) => (
          <div key={i} className="skeleton" style={{ height: 62, borderRadius: 12 }} />
        ))}
      </div>
    );
  }
  if (error) {
    return (
      <div className="card error-state" role="alert">
        Couldn&apos;t load alerts.
        <br />
        <button type="button" onClick={reload}>
          Try again
        </button>
      </div>
    );
  }
  if (!data?.length) {
    return (
      <p className="card empty-state">
        No alerts yet. You&apos;ll see big price moves on your watchlist here.
      </p>
    );
  }

  return (
    <ul className="watchlist__alerts">
      {data.map((a) => (
        <li key={a.id}>
          <Link to={`/stock/${a.symbol}`} className={`alert-card alert-card--${a.direction}`}>
            <span className="alert-card__icon" aria-hidden="true">
              {a.direction === "up" ? "▲" : "▼"}
            </span>
            <span className="alert-card__body">
              <span className="alert-card__message">{a.message}</span>
              <span className="alert-card__meta">
                {formatAlertTime(a.time)}
                {a.reason && ` · ${a.reason}`}
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}