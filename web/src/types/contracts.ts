// TypeScript mirrors of the Earshot contracts. Keep these in sync with CONTEXT.md
// §6 (event schema), §7 (HTTP API) and §8 (DynamoDB). These are the shapes the
// frontend reads from the API and writes to POST /events.

// ---- §8.3 fixed genres ------------------------------------------------------

export type GenreId =
  | "true-crime"
  | "comedy"
  | "news"
  | "technology"
  | "business"
  | "science"
  | "sports"
  | "history";

export interface Genre {
  id: GenreId;
  name: string;
}

// ---- §7.1 EpisodeCard -------------------------------------------------------

/** The reusable card shape used across many responses (CONTEXT §7.1). */
export interface EpisodeCard {
  show_id: string;
  episode_id: string;
  title: string;
  show_title: string;
  image_url: string;
  audio_url: string;
  duration_sec: number;
  genre: GenreId;
  /** Present only in Continue Listening rows and progress-bearing contexts. */
  position_sec?: number;
  /** Present only in trending contexts. */
  plays?: number;
}

// ---- §7.4 GET /home ---------------------------------------------------------

export type HomeRowSource =
  | "progress"
  | "trending"
  | "personalized"
  | "popular_fallback";

export interface HomeRow {
  id: string;
  title: string;
  source: HomeRowSource;
  items: EpisodeCard[];
}

export interface HomeResponse {
  user_id: string;
  generated_at: number;
  degraded: boolean;
  rows: HomeRow[];
}

// ---- §7.3 GET /genres -------------------------------------------------------

export interface GenresResponse {
  genres: Genre[];
}

// ---- §7.3 GET /shows?genre= -------------------------------------------------

export interface ShowSummary {
  show_id: string;
  title: string;
  author: string;
  image_url: string;
  genre: GenreId;
  episode_count: number;
}

export interface ShowsResponse {
  shows: ShowSummary[];
}

// ---- §7.3 GET /shows/{id} ---------------------------------------------------

export interface ShowDetail extends ShowSummary {
  description: string;
}

export interface ShowDetailResponse {
  show: ShowDetail;
  /** EpisodeCards, newest first, without position_sec. */
  episodes: EpisodeCard[];
}

// ---- §7.3 GET /trending -----------------------------------------------------

export interface TrendingResponse {
  date: string;
  items: EpisodeCard[];
}

// ---- §7.3 GET /progress/{id} ------------------------------------------------

export interface ProgressResponse {
  episode_id: string;
  position_sec: number;
  completed: boolean;
  updated_at: number | null;
}

// ---- §7.1 error envelope ----------------------------------------------------

export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}
