import { useCallback, useEffect, useRef, useState } from 'react';

// Runs fn when deps change. Pass null for fn to stay idle. Returns [state, reload].
export function useAsync(fn, deps) {
  const [s, setS] = useState({ status: 'idle', data: null, error: null });
  const latest = useRef(0);
  const run = useCallback(() => {
    const id = ++latest.current;
    if (!fn) { setS({ status: 'idle', data: null, error: null }); return; }
    setS({ status: 'loading', data: null, error: null });
    fn().then(
      (data) => id === latest.current && setS({ status: 'ready', data, error: null }),
      (error) => id === latest.current && setS({ status: 'error', data: null, error })
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return [s, run];
}
