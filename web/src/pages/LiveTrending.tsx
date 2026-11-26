import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Minus, Pause, Play, Sparkle } from "lucide-react";
import { getTrending } from "../lib/api";
import { formatMinutesLabel, formatPlays } from "../lib/format";
import { genreName } from "../lib/genres";
import type { EpisodeCard, TrendingResponse } from "../types/contracts";
import { MediaArtwork } from "../components/MediaArtwork";
import { usePlayer } from "../components/PlayerContext";
import { useUi } from "../components/UiContext";
import { PageHeader, PageMessage } from "./PageHeader";

const POLL_MS = 5000; // CONTEXT §13: Live Trending polls /trending every 5 s
const LIMIT = 20; // the API's maximum (§7.3)

interface Row {
  episode: EpisodeCard;
  rank: number;
  /** Positive = moved up since the last poll; null = new on the list. */
  move: number | null;
  gained: number;
}

/**
 * Today's most-played episodes (GET /trending), refreshed every 5 s while the tab is
 * visible. Each row shows how it moved and how many plays it gained since the last poll.
 */
export function LiveTrending() {
  const [data, setData] = useState<TrendingResponse | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const previous = useRef<Map<string, { rank: number; plays: number }> | null>(null);

  const poll = useCallback(async () => {
    try {
      const res = await getTrending(LIMIT);
      const before = previous.current;
      const next: Row[] = res.items.map((episode, idx) => {
        const rank = idx + 1;
        const old = before?.get(episode.episode_id);
        return {
          episode,
          rank,
          move: before === null ? 0 : old ? old.rank - rank : null,
          gained: old ? Math.max(0, (episode.plays ?? 0) - old.plays) : 0,
        };
      });
      previous.current = new Map(res.items.map((e, idx) => [e.episode_id, { rank: idx + 1, plays: e.plays ?? 0 }]));
      setData(res);
      setRows(next);
      setError(null);
      setUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    let timer: number | undefined;
    const start = () => {
      if (timer !== undefined) return;
      void poll();
      timer = window.setInterval(() => void poll(), POLL_MS);
    };
    const stop = () => {
      window.clearInterval(timer);
      timer = undefined;
    };
    const onVisibility = () => (document.hidden ? stop() : start());
    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [poll]);

  return (
    <>
      <PageHeader
        eyebrow={
          <span className="inline-flex items-center gap-2">
            <span className="relative flex w-2 h-2">
              <span className="absolute inline-flex w-full h-full rounded-full bg-[#E879F9] opacity-75 animate-ping" />
              <span className="relative inline-flex w-2 h-2 rounded-full bg-[#E879F9]" />
            </span>
            Live
          </span>
        }
        title="Trending today"
        subtitle={
          <>
            Plays counted in real time for {data ? formatDate(data.date) : "today"} (UTC). Refreshes every 5 seconds.
          </>
        }
      >
        {updatedAt && (
          <p className="text-xs text-[#A995C8] font-mono tabular-nums" aria-live="polite">
            Updated {updatedAt.toLocaleTimeString()}
          </p>
        )}
      </PageHeader>

      {error && !data && <PageMessage>Couldn't load trending. {error}</PageMessage>}
      {error && data && (
        <p className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 pt-4 text-xs text-[#F0ABFC]">
          The last refresh failed ({error}). Showing the previous list.
        </p>
      )}
      {!data && !error && <PageMessage>Loading trending…</PageMessage>}
      {data && rows.length === 0 && (
        <PageMessage>
          Nothing has been played yet today. Plays show up here within seconds once people start listening.
        </PageMessage>
      )}

      {rows.length > 0 && (
        <ol className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 pt-6 space-y-2.5">
          {rows.map((row) => (
            <TrendingRow key={row.episode.episode_id} row={row} />
          ))}
        </ol>
      )}
    </>
  );
}

function TrendingRow({ row }: { row: Row }) {
  const { play, current, isPlaying } = usePlayer();
  const { openShow } = useUi();
  const { episode, rank, move, gained } = row;
  const isActive = isPlaying && current?.episode_id === episode.episode_id;

  return (
    <li className="group flex items-center gap-4 sm:gap-5 rounded-xl bg-[#160B29]/85 hover:bg-[#1D0F36] border border-purple-300/12 p-3 sm:p-4 transition-colors">
      <span className="rank-numeral text-4xl sm:text-5xl w-12 sm:w-16 text-center shrink-0 tabular-nums">{rank}</span>
      <Movement move={move} />

      <button
        type="button"
        onClick={() => openShow(episode.show_id)}
        aria-label={`Open ${episode.show_title}`}
        className="w-14 h-14 sm:w-16 sm:h-16 rounded-lg overflow-hidden shrink-0 border border-purple-300/15 cursor-pointer"
      >
        <MediaArtwork src={episode.image_url} alt="" title={episode.show_title} className="w-full h-full object-cover" />
      </button>

      <div className="min-w-0 flex-1">
        <h3 className="font-display text-[15px] sm:text-base font-semibold text-[#FAF7FF] truncate">{episode.title}</h3>
        <p className="text-xs text-[#B6A1D5] truncate">
          {episode.show_title} · {genreName(episode.genre)} ·{" "}
          <span className="font-mono tabular-nums">{formatMinutesLabel(episode.duration_sec)}</span>
        </p>
      </div>

      <div className="text-right shrink-0">
        <p className="font-display text-base sm:text-lg font-bold text-[#FAF7FF] tabular-nums">
          {formatPlays(episode.plays ?? 0)}
        </p>
        <p className="text-[11px] text-[#A995C8] tabular-nums">
          {gained > 0 ? <span className="text-[#86EFAC]">+{gained} plays</span> : "plays"}
        </p>
      </div>

      <button
        type="button"
        onClick={() => play(episode)}
        aria-label={`${isActive ? "Pause" : "Play"} ${episode.title}`}
        className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 cursor-pointer transition-colors ${
          isActive ? "bg-[#C084FC] text-[#120722]" : "bg-[#FAF7FF] hover:bg-white text-[#120722]"
        }`}
      >
        {isActive ? (
          <Pause className="w-4 h-4 fill-current" aria-hidden="true" />
        ) : (
          <Play className="w-4 h-4 fill-current ml-0.5" aria-hidden="true" />
        )}
      </button>
    </li>
  );
}

function Movement({ move }: { move: number | null }) {
  const base = "hidden sm:flex w-12 items-center justify-center gap-0.5 text-xs font-semibold tabular-nums shrink-0";
  if (move === null) {
    return (
      <span className={`${base} text-[#E879F9]`} title="New on the list">
        <Sparkle className="w-3.5 h-3.5" aria-hidden="true" />
        New
      </span>
    );
  }
  if (move > 0) {
    return (
      <span className={`${base} text-[#86EFAC]`} title={`Up ${move}`}>
        <ArrowUp className="w-3.5 h-3.5" aria-hidden="true" />
        {move}
      </span>
    );
  }
  if (move < 0) {
    return (
      <span className={`${base} text-[#FDA4AF]`} title={`Down ${-move}`}>
        <ArrowDown className="w-3.5 h-3.5" aria-hidden="true" />
        {-move}
      </span>
    );
  }
  return (
    <span className={`${base} text-[#7C6A99]`} title="No change">
      <Minus className="w-3.5 h-3.5" aria-hidden="true" />
    </span>
  );
}

function formatDate(isoDate: string): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  return Number.isNaN(d.getTime())
    ? isoDate
    : d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", timeZone: "UTC" });
}
