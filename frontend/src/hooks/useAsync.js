import { useCallback, useEffect, useState } from "react";

/** How often live market data is refreshed. The backend caches answers for 30 to 120
 *  seconds and shares them between all users, so this stays far below the API limit. */
export const REFRESH_EVERY_MS = 60_000;

/**
 * Runs an async function (like getStock) and tracks loading / error / data.
 *
 *   const { data, loading, error, reload } = useAsync(() => getStock(symbol), [symbol]);
 *
 * Re-runs whenever a value in `deps` changes. Ignores results from
 * older calls so fast clicking (e.g. chart ranges) never shows stale data.
 *
 * Pass { refreshMs } to also refresh quietly in the background:
 *   useAsync(() => getMarketOverview(), [], { refreshMs: REFRESH_EVERY_MS });
 * A refresh never shows a loading state. If it fails, the last good data stays on
 * screen; if the screen was showing an error, a later successful refresh clears it.
 * Nothing is requested while the browser tab is hidden, and the data is refreshed
 * as soon as the tab is visible again.
 */
export function useAsync(asyncFn, deps = [], { refreshMs } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    asyncFn()
      .then((data) => !cancelled && setState({ data, loading: false, error: null }))
      .catch((error) => !cancelled && setState({ data: null, loading: false, error }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadKey]);

  useEffect(() => {
    if (!refreshMs) return undefined;
    let cancelled = false;

    const refresh = () => {
      if (document.hidden) return;
      asyncFn()
        .then((data) => !cancelled && setState({ data, loading: false, error: null }))
        .catch(() => {}); // keep showing the last good data; the next tick tries again
    };
    const onVisible = () => {
      if (!document.hidden) refresh();
    };

    const timer = setInterval(refresh, refreshMs);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadKey, refreshMs]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  return { ...state, reload };
}
