import { useSearchParams } from "react-router-dom";
import { getGenres, getShows } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import type { Genre, GenreId } from "../types/contracts";
import { ShowTile } from "../components/Cards";
import { PageHeader, PageMessage } from "./PageHeader";

/**
 * Browse by genre (GET /genres, then GET /shows?genre=). The selected genre lives in the
 * address (`/browse?genre=history`), so it survives reloads and can be shared.
 */
export function Browse() {
  const genres = useAsync(getGenres, []);
  const [params, setParams] = useSearchParams();

  const list: Genre[] = genres.status === "ready" ? genres.data.genres : [];
  const requested = params.get("genre");
  const selected = list.find((g) => g.id === requested) ?? list[0];

  return (
    <>
      <PageHeader
        eyebrow="Browse"
        title={selected ? selected.name : "Browse by genre"}
        subtitle="Real podcasts from eight genres. Open a show to see every episode."
      />

      {genres.status === "loading" && <PageMessage>Loading genres…</PageMessage>}
      {genres.status === "error" && <PageMessage>Couldn't load the genres. {genres.error}</PageMessage>}

      {selected && (
        <>
          <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 pt-6">
            <div role="tablist" aria-label="Genres" className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
              {list.map((g) => {
                const isActive = g.id === selected.id;
                return (
                  <button
                    key={g.id}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    onClick={() => setParams({ genre: g.id }, { replace: true })}
                    className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-lg transition-colors whitespace-nowrap shrink-0 cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-400 ${
                      isActive
                        ? "bg-gradient-to-r from-[#9333EA] to-[#A855F7] text-white shadow-[0_6px_22px_rgba(147,51,234,0.38)]"
                        : "bg-[#190D30]/85 hover:bg-[#271449] text-[#CAB9E5] border border-purple-300/12"
                    }`}
                  >
                    {g.name}
                  </button>
                );
              })}
            </div>
          </div>
          <GenreGrid genre={selected.id} />
        </>
      )}
    </>
  );
}

function GenreGrid({ genre }: { genre: GenreId }) {
  const shows = useAsync(() => getShows(genre, 50), [genre]);
  if (shows.status === "loading") return <PageMessage>Loading shows…</PageMessage>;
  if (shows.status === "error") return <PageMessage>Couldn't load the shows. {shows.error}</PageMessage>;
  if (shows.data.shows.length === 0) return <PageMessage>No shows in this genre yet.</PageMessage>;

  return (
    <div className="max-w-[1440px] mx-auto px-5 sm:px-8 lg:px-12 pt-6">
      <p className="text-xs text-[#A995C8] mb-4">
        {shows.data.shows.length} {shows.data.shows.length === 1 ? "show" : "shows"}
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4 sm:gap-5">
        {shows.data.shows.map((show) => (
          <ShowTile key={show.show_id} show={show} wide />
        ))}
      </div>
    </div>
  );
}
