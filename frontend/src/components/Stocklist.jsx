import StockRow, { StockRowSkeleton } from "./StockRow/StockRow";

/**
 * A card listing stocks, with loading, error and empty states built in.
 * Pass the result of useAsync(...) as `state`.
 */
export default function StockList({ state, emptyText = "Nothing here yet.", skeletonCount = 3, limit, onSelect }) {
  const { data, loading, error, reload } = state;

  let content;
  if (loading && !data) {
    content = <StockRowSkeleton count={skeletonCount} />;
  } else if (error) {
    content = (
      <div className="error-state" role="alert">
        Couldn&apos;t load this list.
        <br />
        <button type="button" onClick={reload}>
          Try again
        </button>
      </div>
    );
  } else if (!data?.length) {
    content = <p className="empty-state">{emptyText}</p>;
  } else {
    const items = limit ? data.slice(0, limit) : data;
    content = items.map((s) => <StockRow key={s.symbol} stock={s} onSelect={onSelect} />);
  }

  return (
    <div className="list-card" aria-busy={loading}>
      {content}
    </div>
  );
}