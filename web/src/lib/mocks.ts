// Mock data source (CONTEXT §12 "Mocks first").
//
// In mock mode (VITE_USE_MOCKS=true) the API client answers from the committed fixtures
// in contracts/samples/ instead of the network. api.ts loads this module with a dynamic
// import, so the fixtures end up in a separate chunk that a normal build leaves out.
//
// - /home, /trending and /progress use M2's sample responses as they are.
// - /shows and /shows/{id} are built from catalog.json, with the same shape and rules
//   as §7.3 (sorted by title; episodes newest first, no position). The single-show
//   sample can't answer for the other 47 shows.

import homeJson from "../../../contracts/samples/home.json";
import trendingJson from "../../../contracts/samples/trending.json";
import progressJson from "../../../contracts/samples/progress.json";
import catalogJson from "../../../contracts/samples/catalog.json";

import { ApiRequestError } from "./api";
import { GENRES } from "./genres";
import type {
  EpisodeCard,
  GenreId,
  GenresResponse,
  HomeResponse,
  ProgressResponse,
  ShowDetail,
  ShowDetailResponse,
  ShowsResponse,
  TrendingResponse,
} from "../types/contracts";

interface CatalogEpisode {
  show_id: string;
  episode_id: string;
  title: string;
  audio_url: string;
  duration_sec: number;
  published_at: number;
  image_url: string;
  genre: GenreId;
}

interface Catalog {
  shows: ShowDetail[];
  episodes: CatalogEpisode[];
}

const catalog = catalogJson as unknown as Catalog;

export const home = homeJson as unknown as HomeResponse;
const trendingSample = trendingJson as unknown as TrendingResponse;
let mockPlays = new Map(trendingSample.items.map((e) => [e.episode_id, e.plays ?? 0]));

/**
 * The sample trending list, with a few new plays added on every call and re-sorted, so the
 * Live Trending page visibly updates in mock mode.
 */
export function trending(): TrendingResponse {
  mockPlays = new Map(
    [...mockPlays].map(([id, plays]) => [id, plays + Math.floor(Math.random() * 7)]),
  );
  const items = trendingSample.items
    .map((e) => ({ ...e, plays: mockPlays.get(e.episode_id) ?? 0 }))
    .sort((a, b) => b.plays - a.plays);
  return { ...trendingSample, items };
}
export const genres: GenresResponse = { genres: GENRES };

export function progress(episodeId: string): ProgressResponse {
  const sample = progressJson as unknown as ProgressResponse;
  if (sample.episode_id === episodeId) return sample;
  // Same as the API when there's no progress item yet (§7.3).
  return { episode_id: episodeId, position_sec: 0, completed: false, updated_at: null };
}

export function shows(genre: GenreId, limit: number): ShowsResponse {
  const matching = catalog.shows
    .filter((s) => s.genre === genre)
    .sort((a, b) => a.title.localeCompare(b.title))
    .slice(0, limit)
    .map(({ show_id, title, author, image_url, genre: g, episode_count }) => ({
      show_id,
      title,
      author,
      image_url,
      genre: g,
      episode_count,
    }));
  return { shows: matching };
}

export function showDetail(showId: string): ShowDetailResponse {
  const show = catalog.shows.find((s) => s.show_id === showId);
  if (!show) throw new ApiRequestError("NOT_FOUND", `Unknown show ${showId}`, 404);
  const episodes: EpisodeCard[] = catalog.episodes
    .filter((e) => e.show_id === showId)
    .sort((a, b) => b.published_at - a.published_at)
    .map((e) => ({
      show_id: e.show_id,
      episode_id: e.episode_id,
      title: e.title,
      show_title: show.title,
      image_url: e.image_url,
      audio_url: e.audio_url,
      duration_sec: e.duration_sec,
      genre: e.genre,
    }));
  return { show, episodes };
}
