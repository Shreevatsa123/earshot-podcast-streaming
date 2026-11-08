import type { EpisodeCard as EpisodeCardData } from "../types/contracts";
import { EpisodeCard } from "./EpisodeCard";

interface Props {
  title: string;
  items: EpisodeCardData[];
  onPlay?: (episode: EpisodeCardData) => void;
}

/** A horizontally scrolling Netflix-style row of episode tiles. */
export function Row({ title, items, onPlay }: Props) {
  if (items.length === 0) return null;
  return (
    <section className="row">
      <h2 className="row__title">{title}</h2>
      <div className="row__track">
        {items.map((ep) => (
          <EpisodeCard key={`${ep.episode_id}`} episode={ep} onPlay={onPlay} />
        ))}
      </div>
    </section>
  );
}
