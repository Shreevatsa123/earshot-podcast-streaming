import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { EpisodeCard } from "../types/contracts";

/**
 * Minimal now-playing state for the scaffold. The real player (M1-07) will own the
 * HTML5 <audio> element, resume via GET /progress/{id}, and emit events (M1-08).
 * For M1-01 this just tracks which episode the player bar should display.
 */
interface PlayerState {
  current: EpisodeCard | null;
  play: (episode: EpisodeCard) => void;
}

const PlayerContext = createContext<PlayerState | null>(null);

export function PlayerProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<EpisodeCard | null>(null);
  const value = useMemo<PlayerState>(() => ({ current, play: setCurrent }), [current]);
  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

export function usePlayer(): PlayerState {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error("usePlayer must be used within a PlayerProvider");
  return ctx;
}
