import { useEffect } from "react";
import { Pause, Play, X } from "lucide-react";
import { getShowDetail } from "../lib/api";
import { formatMinutesLabel, progressFraction } from "../lib/format";
import { genreName } from "../lib/genres";
import { useAsync } from "../lib/useAsync";
import { MediaArtwork } from "./MediaArtwork";
import { usePlayer } from "./PlayerContext";

interface Props {
  showId: string | null;
  onClose: () => void;
}

/** Show detail dialog (GET /shows/{id}): header art, description and the episode list. */
export function ShowDetailModal({ showId, onClose }: Props) {
  const state = useAsync(() => getShowDetail(showId as string), [showId], showId !== null);
  const { play, current, isPlaying, currentTime } = usePlayer();

  useEffect(() => {
    if (!showId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [showId, onClose]);

  if (!showId) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="show-dialog-title"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#06020C]/82 backdrop-blur-md p-4 sm:p-6 lg:p-10"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl my-auto rounded-2xl bg-gradient-to-b from-[#1A0D32] via-[#130924] to-[#0D051A] border border-purple-300/18 overflow-hidden shadow-[0_32px_90px_rgba(4,1,12,0.92)]"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close show details"
          className="absolute top-4 right-4 z-20 w-10 h-10 rounded-full bg-[#0D051A]/85 hover:bg-[#241242] text-white border border-purple-300/20 flex items-center justify-center transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-300"
        >
          <X className="w-5 h-5" aria-hidden="true" />
        </button>

        {state.status === "loading" && <div className="h-80 animate-pulse bg-[#1A0D32]" aria-label="Loading show" />}

        {state.status === "error" && (
          <div className="p-10 text-center">
            <h2 id="show-dialog-title" className="font-display text-xl font-bold text-[#FAF7FF] mb-2">
              Couldn't load this show
            </h2>
            <p className="text-sm text-[#A894C9]">{state.error}</p>
          </div>
        )}

        {state.status === "ready" &&
          (() => {
            const { show, episodes } = state.data;
            const latest = episodes[0];
            const latestIsCurrent = latest && current?.episode_id === latest.episode_id;
            return (
              <>
                <div className="relative h-64 sm:h-80 w-full overflow-hidden">
                  <MediaArtwork src={show.image_url} alt="" title={show.title} className="w-full h-full object-cover" />
                  <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-[#180C2F] via-[#160B2A]/60 to-transparent" />
                  <div className="absolute bottom-6 left-6 right-6 sm:left-8 sm:right-8">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-medium text-[#D8B4FE] mb-2">
                      <span>{genreName(show.genre)}</span>
                      <span aria-hidden="true" className="text-purple-300/40">·</span>
                      <span className="tabular-nums">{show.episode_count} episodes</span>
                    </div>
                    <h2
                      id="show-dialog-title"
                      className="font-display text-3xl sm:text-4xl font-extrabold tracking-tight text-[#FAF7FF] text-balance"
                    >
                      {show.title}
                    </h2>
                  </div>
                </div>

                <div className="p-6 sm:p-8 space-y-8">
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                    <div className="lg:col-span-8 space-y-5">
                      {latest && (
                        <button
                          type="button"
                          onClick={() => play(latest)}
                          className="inline-flex items-center gap-2.5 px-6 py-2.5 rounded-lg bg-[#FAF7FF] hover:bg-white text-[#120722] font-semibold text-sm transition-transform active:scale-[0.98] whitespace-nowrap cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-300"
                        >
                          {latestIsCurrent && isPlaying ? (
                            <Pause className="w-4 h-4 fill-current" aria-hidden="true" />
                          ) : (
                            <Play className="w-4 h-4 fill-current" aria-hidden="true" />
                          )}
                          <span>{latestIsCurrent && isPlaying ? "Pause" : "Play latest episode"}</span>
                        </button>
                      )}
                      <p className="text-[15px] leading-relaxed text-[#DCD0EE]">{show.description}</p>
                    </div>

                    <dl className="lg:col-span-4 space-y-2.5 text-sm border-t lg:border-t-0 lg:border-l border-purple-300/12 pt-4 lg:pt-0 lg:pl-6">
                      <div>
                        <dt className="text-xs text-[#9D87BE]">Host</dt>
                        <dd className="text-[#F3ECFF] font-medium">{show.author}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-[#9D87BE]">Genre</dt>
                        <dd className="text-[#F3ECFF] font-medium">{genreName(show.genre)}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-[#9D87BE]">Episodes</dt>
                        <dd className="text-[#F3ECFF] font-medium tabular-nums">{show.episode_count}</dd>
                      </div>
                    </dl>
                  </div>

                  <div className="pt-6 border-t border-purple-300/12">
                    <h3 className="font-display text-xl font-bold text-[#FAF7FF] mb-5">Episodes</h3>
                    <div className="divide-y divide-purple-300/10">
                      {episodes.map((ep, idx) => {
                        const isCurrent = current?.episode_id === ep.episode_id;
                        const pct = isCurrent ? Math.round(progressFraction(currentTime, ep.duration_sec) * 100) : 0;
                        return (
                          <div
                            key={ep.episode_id}
                            className={`py-4 px-3 -mx-3 rounded-xl flex items-center gap-4 transition-colors ${
                              isCurrent ? "bg-[#281449]/75" : "hover:bg-[#21103C]/65"
                            }`}
                          >
                            <span className="font-mono text-sm tabular-nums text-[#A995C8] w-6 text-right shrink-0">
                              {(idx + 1).toString().padStart(2, "0")}
                            </span>
                            <button
                              type="button"
                              onClick={() => play(ep)}
                              aria-label={`${isCurrent && isPlaying ? "Pause" : "Play"} ${ep.title}`}
                              className={`w-11 h-11 rounded-full flex items-center justify-center transition-colors cursor-pointer shrink-0 focus-visible:outline-2 focus-visible:outline-purple-300 ${
                                isCurrent ? "bg-[#C084FC] text-[#120722]" : "bg-[#FAF7FF]/95 text-[#120722] hover:bg-white"
                              }`}
                            >
                              {isCurrent && isPlaying ? (
                                <Pause className="w-4 h-4 fill-current" aria-hidden="true" />
                              ) : (
                                <Play className="w-4 h-4 fill-current ml-0.5" aria-hidden="true" />
                              )}
                            </button>
                            <div className="flex-1 min-w-0">
                              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                                <h4 className="font-display text-[15px] font-semibold text-[#FAF7FF] min-w-0">{ep.title}</h4>
                                <span className="text-xs text-[#B39FD3] font-mono tabular-nums shrink-0">
                                  {formatMinutesLabel(ep.duration_sec)}
                                </span>
                              </div>
                              {pct > 0 && (
                                <div className="mt-2 h-1 max-w-[200px] rounded-full bg-purple-950 overflow-hidden">
                                  <div className="h-full bg-gradient-to-r from-[#9333EA] to-[#D8B4FE]" style={{ width: `${pct}%` }} />
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </>
            );
          })()}
      </div>
    </div>
  );
}
