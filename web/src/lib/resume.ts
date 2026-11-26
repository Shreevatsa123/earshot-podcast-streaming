// Where to start an episode (M1-07, CONTEXT §6 "Progress", S2: resume within ±2 s).

import type { ProgressResponse } from "../types/contracts";

/** Saved positions this close to the end count as finished, so playback starts over. */
export const NEAR_END_SEC = 15;

/** `positionSec` clamped to the episode, or 0 when it's at (or near) the end. */
export function startFrom(positionSec: number, durationSec: number): number {
  if (!Number.isFinite(positionSec) || positionSec <= 0) return 0;
  if (durationSec > 0 && positionSec >= durationSec - NEAR_END_SEC) return 0;
  return Math.floor(positionSec);
}

/**
 * The start position from GET /progress/{id}, or null when the API has nothing saved
 * (`updated_at: null`), in which case the caller keeps its own guess.
 */
export function startFromProgress(progress: ProgressResponse, durationSec: number): number | null {
  if (progress.updated_at === null) return null;
  if (progress.completed) return 0;
  return startFrom(progress.position_sec, durationSec);
}
