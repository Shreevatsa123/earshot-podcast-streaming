import { useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; data: T };

/**
 * Run `load` whenever `deps` change and track loading/error/ready. Results from a stale
 * run (deps changed before it finished) are dropped. Pass `enabled=false` to skip.
 */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[], enabled = true): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    setState({ status: "loading" });
    load()
      .then((data) => active && setState({ status: "ready", data }))
      .catch((err: unknown) =>
        active && setState({ status: "error", error: err instanceof Error ? err.message : String(err) }),
      );
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);

  return state;
}
