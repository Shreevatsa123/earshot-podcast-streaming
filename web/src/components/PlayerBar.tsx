import { usePlayer } from "./PlayerContext";
import { formatDuration, progressFraction } from "../lib/format";

/**
 * Persistent bottom player bar. For the scaffold it reflects the selected episode;
 * the real HTML5 <audio>, resume (GET /progress/{id}) and event emission arrive in
 * M1-07 / M1-08.
 */
export function PlayerBar() {
  const { current } = usePlayer();

  if (!current) {
    return (
      <footer className="player player--empty">
        Pick an episode to start listening
      </footer>
    );
  }

  const fraction = progressFraction(current.position_sec, current.duration_sec);
  const position = current.position_sec ?? 0;

  return (
    <footer className="player">
      <img className="player__art" src={current.image_url} alt="" />
      <div className="player__meta">
        <div className="player__title">{current.title}</div>
        <div className="player__show">{current.show_title}</div>
      </div>
      <div className="player__scrubber">
        <span>{formatDuration(position)}</span>
        <div className="player__bar">
          <span style={{ width: `${Math.round(fraction * 100)}%` }} />
        </div>
        <span>{formatDuration(current.duration_sec)}</span>
      </div>
      <div className="player__controls">
        <button className="player__btn" aria-label="Back 15 seconds">
          ◀◀
        </button>
        <button className="player__play" aria-label="Play">
          ▶
        </button>
        <button className="player__btn" aria-label="Forward 30 seconds">
          ▶▶
        </button>
      </div>
    </footer>
  );
}
