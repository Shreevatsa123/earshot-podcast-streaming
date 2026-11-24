import { createContext, useContext } from "react";

/** App-wide UI actions: open the show detail dialog or the search overlay from anywhere. */
export interface UiActions {
  openShow: (showId: string) => void;
  openSearch: () => void;
}

export const UiContext = createContext<UiActions | null>(null);

export function useUi(): UiActions {
  const ctx = useContext(UiContext);
  if (!ctx) throw new Error("useUi must be used within UiContext.Provider");
  return ctx;
}
