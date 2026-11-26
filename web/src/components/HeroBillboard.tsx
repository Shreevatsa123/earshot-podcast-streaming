import { Info, Pause, Play, Sparkles, TrendingUp } from "lucide-react";
import type { EpisodeCard } from "../types/contracts";
import { formatMinutesLabel, formatPlays } from "../lib/format";
import { genreName } from "../lib/genres";
import { MediaArtwork } from "./MediaArtwork";
import { usePlayer } from "./PlayerContext";
import { useUi } from "./UiContext";

interface Props {
  featured: EpisodeCard[];
  /** True when `featured` comes from today's trending row; otherwise it's a fallback pick. */
  fromTrending: boolean;
  activeIndex: number;
  onSelectIndex: (index: number) => void;
}

/**
 * Full-width spotlight at the top of Home: the selected episode's cover as a backdrop
 * under purple scrims, with a switcher for the other featured episodes.
 */
export function HeroBillboard({ featured, fromTrending, activeIndex, onSelectIndex }: Props) {
  const { play, current, isPlaying } = usePlayer();
  const { openShow } = useUi();
  const episode = featured[activeIndex] ?? featured[0];
  if (!episode) return null;

  const isThisPlaying = isPlaying && current?.episode_id === episode.episode_id;
  const rank = activeIndex + 1;

  return (
    <section
      aria-label="Featured episode"
      className="relative w-full min-h-[72vh] lg:min-h-[78vh] flex items-end overflow-hidden pt-28 pb-14 sm:pb-16"
    >
      {/* The mask fades the whole backdrop into the page gradient, so there's no hard edge. */}
      <div className="absolute inset-0 z-0 [mask-image:linear-gradient(to_bottom,black_62%,transparent)]">
        <MediaArtwork
          key={episode.episode_id}
          src={episode.image_url}
          alt=""
          title={episode.show_title}
          loading="eager"
          className="w-full h-full object-cover object-center scale-110 blur-[3px]"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-r from-[#090411]/95 via-[#140826]/80 to-[#1D0B38]/35"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-t from-[#120722]/70 via-[#120722]/35 to-[#090411]/30"
        />
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[radial-gradient(ellipse_65%_55%_at_18%_65%,rgba(126,34,206,0.28),transparent_70%)]"
        />
      </div>

      <div className="relative z-10 w-full max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 flex flex-col lg:flex-row lg:items-end justify-between gap-10">
        <div className="max-w-2xl">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs sm:text-sm font-medium text-[#D8B4FE] mb-4">
            <span className="inline-flex items-center gap-1.5 font-semibold text-[#E9D5FF]">
              {fromTrending ? (
                <>
                  <TrendingUp className="w-4 h-4" aria-hidden="true" />#{rank} on Earshot today
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" aria-hidden="true" />
                  Featured on Earshot
                </>
              )}
            </span>
            <span aria-hidden="true" className="text-purple-300/40">·</span>
            <span>{genreName(episode.genre)}</span>
            {fromTrending && episode.plays !== undefined && (
              <>
                <span aria-hidden="true" className="text-purple-300/40">·</span>
                <span className="tabular-nums">{formatPlays(episode.plays)} plays</span>
              </>
            )}
          </div>

          <h1 className="font-display text-[clamp(2.1rem,4.2vw,4rem)] font-extrabold leading-[1.05] tracking-tight text-[#FAF7FF] text-balance mb-4 line-clamp-3">
            {episode.title}
          </h1>

          <p className="text-sm sm:text-base text-[#DCD0EE] mb-8">
            <span className="text-[#E9D5FF] font-medium">{episode.show_title}</span>
            <span aria-hidden="true" className="mx-2 text-purple-300/40">·</span>
            <span className="font-mono tabular-nums">{formatMinutesLabel(episode.duration_sec)}</span>
          </p>

          <div className="flex flex-wrap items-center gap-3.5">
            <button
              type="button"
              onClick={() => play(episode)}
              className="inline-flex items-center justify-center gap-2.5 px-6 py-3 rounded-lg bg-[#F8F5FF] hover:bg-white text-[#120722] font-semibold text-sm sm:text-[15px] transition-transform duration-150 active:scale-[0.98] whitespace-nowrap cursor-pointer shadow-[0_8px_30px_rgba(147,51,234,0.35)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300"
            >
              {isThisPlaying ? (
                <Pause className="w-4 h-4 fill-current" aria-hidden="true" />
              ) : (
                <Play className="w-4 h-4 fill-current" aria-hidden="true" />
              )}
              <span>{isThisPlaying ? "Pause" : "Play Episode"}</span>
            </button>

            <button
              type="button"
              onClick={() => openShow(episode.show_id)}
              className="inline-flex items-center justify-center gap-2.5 px-6 py-3 rounded-lg bg-[#271546]/80 hover:bg-[#351D5E]/90 text-[#F5F1FC] border border-purple-300/20 font-semibold text-sm sm:text-[15px] backdrop-blur-sm transition-colors duration-150 whitespace-nowrap cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300"
            >
              <Info className="w-4 h-4 text-[#D8B4FE]" aria-hidden="true" />
              <span>More Info</span>
            </button>
          </div>
        </div>

        {featured.length > 1 && (
          <div aria-label="Switch featured episode" className="flex lg:flex-col items-stretch gap-2.5 lg:w-72 shrink-0">
            {featured.map((item, idx) => {
              const isSelected = idx === activeIndex;
              return (
                <button
                  key={item.episode_id}
                  type="button"
                  onClick={() => onSelectIndex(idx)}
                  aria-pressed={isSelected}
                  className={`text-left px-3.5 py-2.5 rounded-lg border transition-colors duration-150 cursor-pointer flex-1 lg:flex-none min-w-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 ${
                    isSelected
                      ? "bg-[#251343]/90 border-[#C084FC]/45 text-white"
                      : "bg-[#120822]/60 hover:bg-[#1D0F36]/80 border-purple-300/10 text-[#BBA9D6]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <span className="font-mono text-[11px] tabular-nums text-[#C084FC]">0{idx + 1}</span>
                    <span className="text-[11px] text-[#A893C7] truncate">{genreName(item.genre)}</span>
                  </div>
                  <div className="font-display text-sm font-semibold truncate">{item.show_title}</div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
