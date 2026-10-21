import { useCallback, useEffect, useState } from "react";

/**
 * Runs an async function (like getStock) and tracks loading / error / data.
 *
 *   const { data, loading, error, reload } = useAsync(() => getStock(symbol), [symbol]);
 *
 * Re-runs whenever a value in `deps` changes. Ignores results from
 * older calls so fast clicking (e.g. chart ranges) never shows stale data.
 */
export function useAsync(asyncFn, deps = []) {
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

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  return { ...state, reload };
}