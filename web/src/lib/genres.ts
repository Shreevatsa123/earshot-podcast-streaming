// The 8 fixed genres (CONTEXT §8.3), used for labels and the genre filter.

import type { Genre, GenreId } from "../types/contracts";

export const GENRES: Genre[] = [
  { id: "true-crime", name: "True Crime" },
  { id: "comedy", name: "Comedy" },
  { id: "news", name: "News" },
  { id: "technology", name: "Technology" },
  { id: "business", name: "Business" },
  { id: "science", name: "Science" },
  { id: "sports", name: "Sports" },
  { id: "history", name: "History" },
];

const NAMES = new Map(GENRES.map((g) => [g.id, g.name]));

/** Display name for a genre id, e.g. "true-crime" -> "True Crime". */
export function genreName(id: GenreId | string): string {
  return NAMES.get(id as GenreId) ?? id;
}
