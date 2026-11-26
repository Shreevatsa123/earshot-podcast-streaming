import { useEffect, useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";
import { getShows } from "../lib/api";
import { GENRES, genreName } from "../lib/genres";
import { useAsync } from "../lib/useAsync";
import type { ShowSummary } from "../types/contracts";
import { MediaArtwork } from "./MediaArtwork";
import { useUi } from "./UiContext";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Full-screen show search. The API has no search route (§7.3), so this loads each genre's
 * show list once (8 × GET /shows, at most 50 each) and filters on the client by title,
 * host and genre.
 */
export function SearchOverlay({ isOpen, onClose }: Props) {
  const { openShow } = useUi();
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  // Load the show lists the first time search opens, then keep them.
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (isOpen) setLoaded(true);
  }, [isOpen]);

  const state = useAsync(
    async () => {
      const lists = await Promise.all(GENRES.map((g) => getShows(g.id, 50)));
      return lists.flatMap((l) => l.shows).sort((a, b) => a.title.localeCompare(b.title));
    },
    [],
    loaded,
  );

  useEffect(() => {
    if (!isOpen) return;
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 40);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener("keydown", onKey);
    };
  }, [isOpen, onClose]);

  const normalized = query.trim().toLowerCase();
  const matches = useMemo<ShowSummary[]>(() => {
    if (state.status !== "ready") return [];
    if (!normalized) return state.data;
    return state.data.filter(
      (s) =>
        s.title.toLowerCase().includes(normalized) ||
        s.author.toLowerCase().includes(normalized) ||
        genreName(s.genre).toLowerCase().includes(normalized),
    );
  }, [state, normalized]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Search podcasts"
      className="fixed inset-0 z-50 bg-[#080311]/92 backdrop-blur-xl overflow-y-auto"
      onClick={onClose}
    >
      <div className="max-w-5xl mx-auto px-5 sm:px-8 py-8 sm:py-12" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 pb-4 border-b border-purple-300/20 mb-8">
          <Search className="w-5 h-5 text-[#C084FC] shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search shows, hosts or genres..."
            aria-label="Search shows, hosts or genres"
            className="w-full bg-transparent text-lg sm:text-2xl font-display font-medium text-[#FAF7FF] placeholder:text-[#8E79B0] focus:outline-none"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="text-xs font-medium text-[#B9A7D6] hover:text-white px-2.5 py-1 cursor-pointer whitespace-nowrap"
            >
              Clear
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close search"
            className="w-10 h-10 rounded-full bg-[#22113E] hover:bg-[#311A59] text-white flex items-center justify-center shrink-0 cursor-pointer"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {state.status === "loading" && <p className="py-16 text-center text-sm text-[#A894C9]">Loading shows…</p>}
        {state.status === "error" && (
          <p className="py-16 text-center text-sm text-[#A894C9]">Couldn't load shows. {state.error}</p>
        )}

        {state.status === "ready" &&
          (matches.length === 0 ? (
            <div className="py-16 text-center">
              <p className="font-display text-xl font-semibold text-[#FAF7FF] mb-2">No results for “{query}”</p>
              <p className="text-sm text-[#A894C9]">Try a genre like History or Comedy, or a host's name.</p>
            </div>
          ) : (
            <div>
              <h3 className="font-display text-sm font-semibold text-[#C084FC] mb-4">
                {normalized ? `Matching shows (${matches.length})` : `All shows (${matches.length})`}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {matches.map((show) => (
                  <button
                    key={show.show_id}
                    type="button"
                    onClick={() => {
                      onClose();
                      openShow(show.show_id);
                    }}
                    className="text-left flex items-center gap-3.5 p-3 rounded-xl bg-[#180C2D]/90 hover:bg-[#241242] border border-purple-300/12 transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-400"
                  >
                    <div className="w-16 h-16 rounded-lg overflow-hidden shrink-0">
                      <MediaArtwork src={show.image_url} alt="" title={show.title} className="w-full h-full object-cover" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] text-[#C084FC] truncate">
                        {genreName(show.genre)} · {show.episode_count} episodes
                      </p>
                      <h4 className="font-display text-sm font-bold text-[#FAF7FF] truncate">{show.title}</h4>
                      <p className="text-xs text-[#A894C9] truncate">{show.author}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}
