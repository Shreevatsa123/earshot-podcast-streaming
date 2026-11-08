import { useEffect, useState } from "react";
import { getHome } from "../lib/api";
import type { EpisodeCard, HomeResponse } from "../types/contracts";
import { Row } from "../components/Row";
import { usePlayer } from "../components/PlayerContext";

/**
 * Home page (CONTEXT §7.4). Renders a Netflix billboard from the first trending item
 * plus one row per `rows[]` entry, in order. Shows a banner when `degraded` is true.
 * Full page polish (genre browse links, etc.) is M1-06; this proves the scaffold end
 * to end against the mock fixture.
 */
export function Home() {
  const { play } = usePlayer();
  const [data, setData] = useState<HomeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getHome()
      .then((res) => active && setData(res))
      .catch((err) => active && setError(err.message ?? "Failed to load home"));
    return () => {
      active = false;
    };
  }, []);

  if (error) return <div className="error">Could not load home. {error}</div>;
  if (!data) return <div className="loading">Loading…</div>;

  const hero = pickHero(data);

  return (
    <>
      {hero && <Hero episode={hero} onPlay={play} />}
      {data.degraded && (
        <div className="degraded-banner">
          Personalized picks are unavailable right now, showing popular episodes instead.
        </div>
      )}
      <div className="rows">
        {data.rows.map((row) => (
          <Row key={row.id} title={row.title} items={row.items} onPlay={play} />
        ))}
      </div>
    </>
  );
}

function pickHero(data: HomeResponse): EpisodeCard | null {
  const trending = data.rows.find((r) => r.source === "trending");
  if (trending && trending.items.length > 0) return trending.items[0];
  const first = data.rows.find((r) => r.items.length > 0);
  return first ? first.items[0] : null;
}

function Hero({
  episode,
  onPlay,
}: {
  episode: EpisodeCard;
  onPlay: (ep: EpisodeCard) => void;
}) {
  return (
    <section className="hero" style={{ backgroundImage: `url(${episode.image_url})` }}>
      <div className="hero__inner">
        <div className="hero__eyebrow">▶ Top of the charts</div>
        <h1 className="hero__title">{episode.title}</h1>
        <div className="hero__meta">
          {episode.show_title}
          {episode.plays !== undefined ? ` · ${episode.plays} plays today` : ""}
        </div>
        <div className="hero__actions">
          <button className="btn btn--play" onClick={() => onPlay(episode)}>
            ▶ Play
          </button>
          <button className="btn btn--ghost">ℹ More Info</button>
        </div>
      </div>
    </section>
  );
}
