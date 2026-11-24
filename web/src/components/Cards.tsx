import type { KeyboardEvent } from "react";
import { Info, Pause, Play, TrendingUp } from "lucide-react";
import type { EpisodeCard, ShowSummary } from "../types/contracts";
import { formatMinutesLabel, formatPlays, progressFraction } from "../lib/format";
import { genreName } from "../lib/genres";
import { MediaArtwork } from "./MediaArtwork";
import { usePlayer } from "./PlayerContext";
import { useUi } from "./UiContext";

const cardFrame =
  "relative rounded-xl bg-[#160B29]/90 border border-purple-300/12 overflow-hidden transition-transform duration-200 ease-out hover:-translate-y-1 hover:border-purple-300/30";

function onActivate(handler: () => void) {
  return {
    role: "button" as const,
    tabIndex: 0,
    onClick: handler,
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handler();
      }
    },
  };
}

/** Wide card for Continue Listening: artwork, resume bar and time left. */
export function ContinueCard({ episode }: { episode: EpisodeCard }) {
  const { play, current, isPlaying } = usePlayer();
  const { openShow } = useUi();
  const isActive = isPlaying && current?.episode_id === episode.episode_id;
  const pct = Math.max(4, Math.round(progressFraction(episode.position_sec, episode.duration_sec) * 100));
  const remaining = Math.max(0, episode.duration_sec - (episode.position_sec ?? 0));

  return (
    <article className={`group w-[290px] sm:w-[330px] shrink-0 snap-start ${cardFrame}`}>
      <div
        {...onActivate(() => play(episode))}
        aria-label={`${isActive ? "Pause" : "Resume"} ${episode.title}`}
        className="relative aspect-[16/9] overflow-hidden cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-400"
      >
        <MediaArtwork
          src={episode.image_url}
          alt=""
          title={episode.show_title}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
        />
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-[#120823] via-[#120823]/25 to-transparent" />
        <div className="absolute inset-0 flex items-center justify-center">
          <span
            className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-150 shadow-[0_8px_24px_rgba(0,0,0,0.65)] ${
              isActive
                ? "bg-[#C084FC] text-[#120722]"
                : "bg-[#FAF7FF]/95 text-[#120722] opacity-90 group-hover:opacity-100 group-hover:scale-105"
            }`}
          >
            {isActive ? (
              <Pause className="w-5 h-5 fill-current" aria-hidden="true" />
            ) : (
              <Play className="w-5 h-5 fill-current ml-0.5" aria-hidden="true" />
            )}
          </span>
        </div>
        <div className="absolute bottom-0 inset-x-0 h-1 bg-purple-950/90">
          <div className="h-full bg-gradient-to-r from-[#9333EA] to-[#D8B4FE]" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="p-4 flex flex-col gap-1.5">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className="truncate font-medium text-[#D8B4FE]">{episode.show_title}</span>
          <span className="font-mono tabular-nums shrink-0 text-[#B6A1D5]">{formatMinutesLabel(remaining)} left</span>
        </div>
        <h3 className="font-display text-base font-semibold text-[#FAF7FF] truncate">{episode.title}</h3>
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-[#9D88BE] truncate">{genreName(episode.genre)}</span>
          <button
            type="button"
            onClick={() => openShow(episode.show_id)}
            className="text-xs font-medium text-[#D8B4FE] hover:text-white transition-colors whitespace-nowrap cursor-pointer"
          >
            Episodes
          </button>
        </div>
      </div>
    </article>
  );
}

/**
 * Episode card for Trending, Recommended and Popular rows. With `rank`, a large outlined
 * number sits beside it ("Top Podcasts Today").
 */
export function EpisodeTile({ episode, rank }: { episode: EpisodeCard; rank?: number }) {
  const { play, current, isPlaying } = usePlayer();
  const { openShow } = useUi();
  const isActive = isPlaying && current?.episode_id === episode.episode_id;

  return (
    <article
      className={`group relative shrink-0 snap-start flex items-end ${
        rank !== undefined ? "w-[300px] sm:w-[340px]" : "w-[240px] sm:w-[260px]"
      }`}
    >
      {rank !== undefined && (
        <span
          aria-hidden="true"
          className="rank-numeral text-[150px] sm:text-[190px] select-none -mr-5 pb-2 z-0 shrink-0 tabular-nums"
        >
          {rank}
        </span>
      )}

      <div className={`z-10 flex-1 min-w-0 ${cardFrame}`}>
        <div
          {...onActivate(() => openShow(episode.show_id))}
          aria-label={`Open ${episode.show_title}`}
          className={`relative overflow-hidden cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-400 ${
            rank !== undefined ? "aspect-[4/3]" : "aspect-square"
          }`}
        >
          <MediaArtwork
            src={episode.image_url}
            alt=""
            title={episode.show_title}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
          <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-[#150A28] via-transparent to-transparent" />
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              play(episode);
            }}
            aria-label={`${isActive ? "Pause" : "Play"} ${episode.title}`}
            className={`absolute bottom-3 right-3 w-10 h-10 rounded-full flex items-center justify-center transition-all duration-150 cursor-pointer shadow-[0_6px_20px_rgba(0,0,0,0.65)] focus-visible:outline-2 focus-visible:outline-purple-300 ${
              isActive
                ? "bg-[#C084FC] text-[#120722]"
                : "bg-[#FAF7FF] text-[#120722] opacity-95 sm:opacity-0 sm:group-hover:opacity-100 sm:translate-y-1 sm:group-hover:translate-y-0 focus-visible:opacity-100"
            }`}
          >
            {isActive ? (
              <Pause className="w-4 h-4 fill-current" aria-hidden="true" />
            ) : (
              <Play className="w-4 h-4 fill-current ml-0.5" aria-hidden="true" />
            )}
          </button>
        </div>

        <div className="p-4">
          <div className="flex items-center gap-1.5 text-xs text-[#B6A1D5] mb-1 min-w-0">
            <span className="truncate">{genreName(episode.genre)}</span>
            <span aria-hidden="true" className="text-purple-300/35">·</span>
            <span className="font-mono tabular-nums shrink-0">{formatMinutesLabel(episode.duration_sec)}</span>
          </div>
          <h3 className="font-display text-[15px] font-bold leading-snug text-[#FAF7FF] line-clamp-2 min-h-[2.6rem] mb-2">
            {episode.title}
          </h3>
          <div className="flex items-center justify-between gap-2 pt-2.5 border-t border-purple-300/10">
            {episode.plays !== undefined ? (
              <span className="inline-flex items-center gap-1 text-xs text-[#D8B4FE] tabular-nums truncate">
                <TrendingUp className="w-3.5 h-3.5" aria-hidden="true" />
                {formatPlays(episode.plays)} plays today
              </span>
            ) : (
              <span className="text-xs text-[#B8A5D8] truncate">{episode.show_title}</span>
            )}
            <button
              type="button"
              onClick={() => openShow(episode.show_id)}
              aria-label={`Details for ${episode.show_title}`}
              className="w-8 h-8 rounded-lg flex items-center justify-center bg-[#21113C] hover:bg-[#2F1954] border border-purple-300/15 text-[#CBB8E6] transition-colors cursor-pointer shrink-0 focus-visible:outline-2 focus-visible:outline-purple-400"
            >
              <Info className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

/** Show card for genre lists and search: artwork, genre, episode count, author. */
export function ShowTile({ show, wide = false }: { show: ShowSummary; wide?: boolean }) {
  const { openShow } = useUi();
  return (
    <article className={`group ${wide ? "w-full" : "w-[220px] sm:w-[240px] shrink-0 snap-start"} ${cardFrame}`}>
      <div
        {...onActivate(() => openShow(show.show_id))}
        aria-label={`Open ${show.title}`}
        className="relative aspect-square overflow-hidden cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-400"
      >
        <MediaArtwork
          src={show.image_url}
          alt=""
          title={show.title}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
        />
        <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-[#150A28] via-transparent to-transparent" />
      </div>
      <div className="p-4">
        <div className="flex items-center gap-1.5 text-xs text-[#B6A1D5] mb-1">
          <span className="truncate">{genreName(show.genre)}</span>
          <span aria-hidden="true" className="text-purple-300/35">·</span>
          <span className="tabular-nums shrink-0">
            {show.episode_count} {show.episode_count === 1 ? "Ep" : "Eps"}
          </span>
        </div>
        <h3 className="font-display text-[15px] font-bold leading-snug text-[#FAF7FF] line-clamp-2 min-h-[2.6rem]">
          {show.title}
        </h3>
        <p className="text-xs text-[#A894C9] truncate mt-1">{show.author}</p>
      </div>
    </article>
  );
}
