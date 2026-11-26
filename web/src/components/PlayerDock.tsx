import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  ChevronUp,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { getShowDetail } from "../lib/api";
import { formatDuration, formatMinutesLabel } from "../lib/format";
import { genreName } from "../lib/genres";
import { useAsync } from "../lib/useAsync";
import { MediaArtwork } from "./MediaArtwork";
import { usePlayer } from "./PlayerContext";
import { useUi } from "./UiContext";

// Fixed bar heights (%) and delays for the decorative equalizer in the expanded view.
const EQ_BARS = Array.from({ length: 24 }, (_, i) => ({
  height: 35 + ((i * 37) % 60),
  delay: `${((i * 0.13) % 1).toFixed(2)}s`,
}));

/** Persistent bottom player, plus an expanded full-screen view. Hidden until something plays. */
export function PlayerDock() {
  const player = usePlayer();
  const { openShow } = useUi();
  const [expanded, setExpanded] = useState(false);
  const { current, isPlaying, currentTime, duration } = player;

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  if (!current) return null;

  const pct = Math.min(100, Math.max(0, (currentTime / Math.max(1, duration)) * 100));
  const iconBtn =
    "w-9 h-9 rounded-full flex items-center justify-center text-[#D8B4FE] hover:text-white hover:bg-[#251343] transition-colors cursor-pointer";

  const volumeControl = (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={player.toggleMute}
        aria-label={player.isMuted ? "Unmute" : "Mute"}
        className="text-[#D8B4FE] hover:text-white cursor-pointer"
      >
        {player.isMuted || player.volume === 0 ? (
          <VolumeX className="w-4 h-4" aria-hidden="true" />
        ) : (
          <Volume2 className="w-4 h-4" aria-hidden="true" />
        )}
      </button>
      <input
        type="range"
        min={0}
        max={1}
        step={0.02}
        value={player.isMuted ? 0 : player.volume}
        onChange={(e) => player.setVolume(Number(e.target.value))}
        aria-label="Volume"
        className="w-20 accent-[#C084FC] cursor-pointer h-1"
      />
    </div>
  );

  const speedButton = (
    <button
      type="button"
      onClick={player.cyclePlaybackRate}
      aria-label={`Playback speed ${player.playbackRate}x`}
      className="px-2.5 py-1 rounded-md bg-[#22113E] hover:bg-[#311A59] border border-purple-300/15 font-mono text-xs tabular-nums text-[#E9D5FF] cursor-pointer whitespace-nowrap"
    >
      {player.playbackRate}x
    </button>
  );

  return (
    <>
      {expanded && (
        <ExpandedPlayer
          onMinimize={() => setExpanded(false)}
          volumeControl={volumeControl}
          speedButton={speedButton}
        />
      )}

      <aside
        aria-label="Audio player"
        className="fixed bottom-0 inset-x-0 z-40 bg-[#120723]/95 backdrop-blur-xl border-t border-purple-300/18 shadow-[0_-12px_40px_rgba(4,1,12,0.75)]"
      >
        <div
          className="relative h-1 w-full bg-purple-950/90 cursor-pointer"
          role="slider"
          aria-label="Seek"
          aria-valuemin={0}
          aria-valuemax={Math.round(duration)}
          aria-valuenow={Math.round(currentTime)}
          tabIndex={-1}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            player.seek(((e.clientX - rect.left) / rect.width) * duration);
          }}
        >
          <div
            className="h-full bg-gradient-to-r from-[#9333EA] via-[#C084FC] to-[#E9D5FF] transition-[width] duration-150"
            style={{ width: `${pct}%` }}
          />
        </div>

        <div className="max-w-[1440px] mx-auto px-4 sm:px-8 h-16 sm:h-[74px] flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0 flex-1 sm:flex-initial sm:w-[300px] lg:w-[360px]">
            <button
              type="button"
              onClick={() => setExpanded(true)}
              aria-label="Open full player"
              className="w-11 h-11 sm:w-12 sm:h-12 rounded-lg overflow-hidden shrink-0 border border-purple-300/20 cursor-pointer"
            >
              <MediaArtwork src={current.image_url} alt="" title={current.show_title} className="w-full h-full object-cover" />
            </button>
            <div className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => setExpanded(true)}
                className="block text-left font-display text-sm font-semibold text-[#FAF7FF] hover:text-[#D8B4FE] transition-colors truncate w-full cursor-pointer"
              >
                {current.title}
              </button>
              {player.error ? (
                <p className="text-xs text-[#F0ABFC] truncate">{player.error}</p>
              ) : (
                <button
                  type="button"
                  onClick={() => openShow(current.show_id)}
                  className="block text-left text-xs text-[#B6A1D5] hover:text-white transition-colors truncate w-full cursor-pointer"
                >
                  {current.show_title}
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-4 shrink-0">
            <button type="button" onClick={() => player.skip(-15)} aria-label="Back 15 seconds" className={`hidden sm:flex ${iconBtn}`}>
              <RotateCcw className="w-4 h-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={player.togglePlayPause}
              aria-label={isPlaying ? "Pause" : "Play"}
              className="w-10 h-10 sm:w-11 sm:h-11 rounded-full bg-[#FAF7FF] hover:bg-white text-[#120722] flex items-center justify-center shadow-[0_4px_20px_rgba(168,85,247,0.4)] transition-transform active:scale-95 cursor-pointer"
            >
              {isPlaying ? (
                <Pause className="w-4 h-4 fill-current" aria-hidden="true" />
              ) : (
                <Play className="w-4 h-4 fill-current ml-0.5" aria-hidden="true" />
              )}
            </button>
            <button type="button" onClick={() => player.skip(30)} aria-label="Forward 30 seconds" className={`hidden sm:flex ${iconBtn}`}>
              <RotateCw className="w-4 h-4" aria-hidden="true" />
            </button>
            <span className="hidden lg:inline-block font-mono text-xs tabular-nums text-[#B4A0D4] ml-2">
              {formatDuration(currentTime)} / {formatDuration(duration)}
            </span>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            <div className="hidden sm:block">{speedButton}</div>
            <div className="hidden lg:block">{volumeControl}</div>
            <button
              type="button"
              onClick={() => setExpanded(true)}
              aria-label="Expand player"
              className="w-9 h-9 rounded-lg bg-[#22113E] hover:bg-[#311A59] border border-purple-300/15 text-[#E9D5FF] flex items-center justify-center cursor-pointer"
            >
              <ChevronUp className="w-4 h-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => {
                setExpanded(false);
                player.close();
              }}
              aria-label="Stop and close player"
              className="w-9 h-9 rounded-lg hover:bg-[#22113E] text-[#A894C9] hover:text-white flex items-center justify-center cursor-pointer"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

function ExpandedPlayer({
  onMinimize,
  volumeControl,
  speedButton,
}: {
  onMinimize: () => void;
  volumeControl: ReactNode;
  speedButton: ReactNode;
}) {
  const player = usePlayer();
  const { openShow } = useUi();
  const current = player.current!;
  const more = useAsync(() => getShowDetail(current.show_id), [current.show_id]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Now playing"
      className="fixed inset-0 z-50 flex flex-col bg-gradient-to-b from-[#170A2E] via-[#100620] to-[#080310] overflow-y-auto pb-24"
    >
      <div className="max-w-[1200px] w-full mx-auto px-6 py-5 flex items-center justify-between gap-4 border-b border-purple-300/12">
        <div className="min-w-0">
          <p className="text-xs font-medium text-[#C084FC] truncate">Now listening · {genreName(current.genre)}</p>
          <button
            type="button"
            onClick={() => {
              onMinimize();
              openShow(current.show_id);
            }}
            className="font-display text-base font-bold text-[#FAF7FF] hover:text-[#D8B4FE] transition-colors truncate cursor-pointer"
          >
            {current.show_title}
          </button>
        </div>
        <button
          type="button"
          onClick={onMinimize}
          aria-label="Minimize player"
          className="w-10 h-10 rounded-full bg-[#241242] hover:bg-[#321A5B] border border-purple-300/18 text-white flex items-center justify-center transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" aria-hidden="true" />
        </button>
      </div>

      <div className="max-w-[1200px] w-full mx-auto px-6 py-8 lg:py-10 grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 flex-1">
        <div className="lg:col-span-6 space-y-6">
          <div className="relative aspect-[16/10] rounded-2xl overflow-hidden border border-purple-300/18 shadow-[0_24px_70px_rgba(4,1,12,0.85)]">
            <MediaArtwork src={current.image_url} alt="" title={current.show_title} className="w-full h-full object-cover" />
            <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-[#120722]/90 via-transparent to-transparent" />
            <div
              aria-hidden="true"
              className={`absolute bottom-4 inset-x-6 h-12 flex items-end justify-between gap-1 ${player.isPlaying ? "" : "eq-paused"}`}
            >
              {EQ_BARS.map((bar, idx) => (
                <span
                  key={idx}
                  className="eq-bar flex-1 rounded-full bg-gradient-to-t from-[#9333EA]/80 via-[#C084FC] to-[#F5D0FE]"
                  style={{ height: `${bar.height}%`, animationDelay: bar.delay }}
                />
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs text-[#C084FC] font-medium mb-1">{current.show_title}</p>
            <h2 className="font-display text-2xl sm:text-3xl font-bold text-[#FAF7FF] text-balance">{current.title}</h2>
          </div>

          <div className="space-y-2">
            <input
              type="range"
              min={0}
              max={Math.max(1, Math.floor(player.duration))}
              value={Math.min(Math.floor(player.duration), Math.floor(player.currentTime))}
              onChange={(e) => player.seek(Number(e.target.value))}
              aria-label="Seek"
              className="w-full accent-[#C084FC] cursor-pointer h-1.5"
            />
            <div className="flex items-center justify-between font-mono text-xs tabular-nums text-[#B39FD3]">
              <span>{formatDuration(player.currentTime)}</span>
              <span>-{formatDuration(Math.max(0, player.duration - player.currentTime))}</span>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2">
            {speedButton}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => player.skip(-15)}
                aria-label="Back 15 seconds"
                className="w-10 h-10 rounded-full flex items-center justify-center text-[#E9D5FF] hover:bg-[#271447] cursor-pointer"
              >
                <RotateCcw className="w-5 h-5" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={player.togglePlayPause}
                aria-label={player.isPlaying ? "Pause" : "Play"}
                className="w-14 h-14 rounded-full bg-[#FAF7FF] hover:bg-white text-[#120722] flex items-center justify-center shadow-[0_10px_30px_rgba(168,85,247,0.45)] cursor-pointer transition-transform active:scale-95"
              >
                {player.isPlaying ? (
                  <Pause className="w-6 h-6 fill-current" aria-hidden="true" />
                ) : (
                  <Play className="w-6 h-6 fill-current ml-0.5" aria-hidden="true" />
                )}
              </button>
              <button
                type="button"
                onClick={() => player.skip(30)}
                aria-label="Forward 30 seconds"
                className="w-10 h-10 rounded-full flex items-center justify-center text-[#E9D5FF] hover:bg-[#271447] cursor-pointer"
              >
                <RotateCw className="w-5 h-5" aria-hidden="true" />
              </button>
            </div>
            {volumeControl}
          </div>
        </div>

        <div className="lg:col-span-6 rounded-2xl bg-[#160B29]/90 border border-purple-300/14 p-6 flex flex-col">
          <h3 className="font-display text-base font-bold text-[#FAF7FF] border-b border-purple-300/12 pb-4 mb-3">
            More from {current.show_title}
          </h3>
          {more.status === "loading" && <p className="text-sm text-[#A894C9]">Loading episodes…</p>}
          {more.status === "error" && <p className="text-sm text-[#A894C9]">Couldn't load episodes.</p>}
          {more.status === "ready" && (
            <div className="space-y-2 overflow-y-auto max-h-[55vh] pr-1">
              {more.data.episodes.slice(0, 12).map((ep) => {
                const isCurrent = ep.episode_id === current.episode_id;
                return (
                  <button
                    key={ep.episode_id}
                    type="button"
                    onClick={() => player.play(ep)}
                    className={`w-full text-left px-4 py-3 rounded-xl flex items-center justify-between gap-4 transition-colors cursor-pointer ${
                      isCurrent
                        ? "bg-[#2C1650] border border-[#C084FC]/40 text-white"
                        : "bg-[#1C0E34]/60 hover:bg-[#261445] border border-transparent text-[#D6C7EE]"
                    }`}
                  >
                    <span className="text-sm font-medium line-clamp-2">{ep.title}</span>
                    <span className="font-mono text-xs tabular-nums text-[#B4A0D4] shrink-0">
                      {formatMinutesLabel(ep.duration_sec)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
