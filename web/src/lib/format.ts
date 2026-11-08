// Small display helpers.

/** Seconds -> "H:MM:SS" or "M:SS". */
export function formatDuration(totalSec: number): string {
  if (!Number.isFinite(totalSec) || totalSec < 0) return "0:00";
  const sec = Math.floor(totalSec % 60);
  const min = Math.floor((totalSec / 60) % 60);
  const hr = Math.floor(totalSec / 3600);
  const mm = min.toString().padStart(2, "0");
  const ss = sec.toString().padStart(2, "0");
  return hr > 0 ? `${hr}:${mm}:${ss}` : `${min}:${ss}`;
}

/** Fraction 0..1 of the episode already listened to. */
export function progressFraction(position?: number, duration?: number): number {
  if (!position || !duration || duration <= 0) return 0;
  return Math.min(1, Math.max(0, position / duration));
}

/** Compact play count, e.g. 1234 -> "1.2K". */
export function formatPlays(plays: number): string {
  if (plays < 1000) return `${plays}`;
  return `${(plays / 1000).toFixed(1).replace(/\.0$/, "")}K`;
}
