import { useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { getHome, getShows } from "../lib/api";
import { GENRES, genreName } from "../lib/genres";
import { useAsync } from "../lib/useAsync";
import type { EpisodeCard, GenreId, HomeResponse, HomeRow } from "../types/contracts";
import { HeroBillboard } from "../components/HeroBillboard";
import { ContinueCard, EpisodeTile, ShowTile } from "../components/Cards";
import { Shelf } from "../components/Shelf";

const FEATURED_COUNT = 4;

/**
 * Home (GET /home, CONTEXT §7.4): hero spotlight, genre filter, then one row per
 * `rows[]` entry in the order the API sends them.
 */
export function Home() {
  const home = useAsync(getHome, []);
  const [heroIndex, setHeroIndex] = useState(0);
  const [genre, setGenre] = useState<GenreId | null>(null);

  const featured = useMemo(() => (home.status === "ready" ? pickFeatured(home.data) : []), [home]);

  if (home.status === "loading") return <PageMessage text="Loading your home page…" />;
  if (home.status === "error") return <PageMessage text={`Couldn't load your home page. ${home.error}`} />;

  return (
    <>
      <HeroBillboard featured={featured} activeIndex={heroIndex} onSelectIndex={setHeroIndex} />

      <GenreFilter selected={genre} onSelect={setGenre} />

      {genre ? (
        <GenreShows genre={genre} />
      ) : (
        <div className="space-y-2 pt-2">
          {home.data.degraded && (
            <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12">
              <p className="flex items-center gap-2 rounded-lg border border-purple-300/20 bg-[#1C0E34]/80 px-4 py-3 text-sm text-[#DCD0EE]">
                <AlertTriangle className="w-4 h-4 text-[#D8B4FE] shrink-0" aria-hidden="true" />
                Personalized picks are taking a break, so you're seeing what's popular on Earshot.
              </p>
            </div>
          )}
          {home.data.rows.map((row) => (
            <HomeShelf key={row.id} row={row} />
          ))}
        </div>
      )}
    </>
  );
}

/** Hero spotlight: the top trending episodes, or the first items if trending is empty. */
function pickFeatured(home: HomeResponse): EpisodeCard[] {
  const trending = home.rows.find((r) => r.source === "trending" && r.items.length > 0);
  const source = trending ?? home.rows.find((r) => r.items.length > 0);
  return source ? source.items.slice(0, FEATURED_COUNT) : [];
}

function HomeShelf({ row }: { row: HomeRow }) {
  if (row.items.length === 0) return null;
  switch (row.source) {
    case "progress":
      return (
        <Shelf title={row.title} subtitle="Pick up right where you paused">
          {row.items.map((ep) => (
            <ContinueCard key={ep.episode_id} episode={ep} />
          ))}
        </Shelf>
      );
    case "trending":
      return (
        <Shelf title="Top Podcasts Today" subtitle="The most-played episodes on Earshot right now">
          {row.items.map((ep, idx) => (
            <EpisodeTile key={ep.episode_id} episode={ep} rank={idx + 1} />
          ))}
        </Shelf>
      );
    case "personalized":
      return (
        <Shelf title={row.title} subtitle="Recommended for you from what people with similar taste play">
          {row.items.map((ep) => (
            <EpisodeTile key={ep.episode_id} episode={ep} />
          ))}
        </Shelf>
      );
    default:
      return (
        <Shelf title={row.title} subtitle="What everyone's listening to this week">
          {row.items.map((ep) => (
            <EpisodeTile key={ep.episode_id} episode={ep} />
          ))}
        </Shelf>
      );
  }
}

function GenreFilter({ selected, onSelect }: { selected: GenreId | null; onSelect: (g: GenreId | null) => void }) {
  const chips: { id: GenreId | null; name: string }[] = [{ id: null, name: "All" }, ...GENRES];
  return (
    <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 pt-4 pb-3">
      <div role="tablist" aria-label="Filter by genre" className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
        {chips.map((chip) => {
          const isActive = selected === chip.id;
          return (
            <button
              key={chip.name}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => onSelect(chip.id)}
              className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-lg transition-colors duration-150 whitespace-nowrap shrink-0 cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-400 ${
                isActive
                  ? "bg-gradient-to-r from-[#9333EA] to-[#A855F7] text-white shadow-[0_6px_22px_rgba(147,51,234,0.38)]"
                  : "bg-[#190D30]/85 hover:bg-[#271449] text-[#CAB9E5] border border-purple-300/12"
              }`}
            >
              {chip.name}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function GenreShows({ genre }: { genre: GenreId }) {
  const state = useAsync(() => getShows(genre, 20), [genre]);
  if (state.status === "loading") return <PageMessage text="Loading shows…" compact />;
  if (state.status === "error") return <PageMessage text={`Couldn't load shows. ${state.error}`} compact />;
  const { shows } = state.data;
  return (
    <div className="pt-2">
      <Shelf title={genreName(genre)} subtitle={`${shows.length} ${shows.length === 1 ? "show" : "shows"} in ${genreName(genre)}`}>
        {shows.map((show) => (
          <ShowTile key={show.show_id} show={show} />
        ))}
      </Shelf>
    </div>
  );
}

function PageMessage({ text, compact = false }: { text: string; compact?: boolean }) {
  return <div className={`${compact ? "py-16" : "pt-40 pb-24"} text-center text-sm text-[#A894C9]`}>{text}</div>;
}
