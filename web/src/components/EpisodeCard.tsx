import type { EpisodeCard as EpisodeCardData } from "../types/contracts";
import { formatPlays, progressFraction } from "../lib/format";

interface Props {
  episode: EpisodeCardData;
  onPlay?: (episode: EpisodeCardData) => void;
}

/**
 * The reusable Netflix-style tile used in every Home row (CONTEXT §7.1 EpisodeCard).
 * Shows a resume bar when `position_sec` is present and a play-count badge when
 * `plays` is present, so one component covers Continue / Trending / Recommended rows.
 */
export function EpisodeCard({ episode, onPlay }: Props) {
  const fraction = progressFraction(episode.position_sec, episode.duration_sec);
  const showProgress = episode.position_sec !== undefined && fraction > 0;

  return (
    <div
      className="card"
      role="button"
      tabIndex={0}
      onClick={() => onPlay?.(episode)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onPlay?.(episode);
      }}
      title={episode.title}
    >
      <div className="card__art">
        <img src={episode.image_url} alt="" loading="lazy" />
        {episode.plays !== undefined && (
          <span className="card__badge">▶ {formatPlays(episode.plays)}</span>
        )}
        <div className="card__play" aria-hidden>
          <span>▶</span>
        </div>
        {showProgress && (
          <div className="card__progress">
            <span style={{ width: `${Math.round(fraction * 100)}%` }} />
          </div>
        )}
      </div>
      <div className="card__body">
        <div className="card__title">{episode.title}</div>
        <div className="card__show">{episode.show_title}</div>
      </div>
    </div>
  );
}
