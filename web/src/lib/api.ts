// Typed API client for the Earshot HTTP API (CONTEXT §7).
//
// Every read route is exposed here. In mock mode (VITE_USE_MOCKS=true) each call
// answers from the committed fixtures instead of the network (see mocks.ts), so the UI
// can be built before M2's API exists. M1-09 switches the app to the real API.
//
// Auth: the real API needs `Authorization: Bearer <access token>` on every route
// except GET /health (§7.1). The auth layer (M1-05) injects the token getter; until
// then it returns null and mock mode is used.

import { getConfig, USE_MOCKS } from "./config";
import type {
  GenreId,
  GenresResponse,
  HomeResponse,
  ProgressResponse,
  ShowDetailResponse,
  ShowsResponse,
  TrendingResponse,
} from "../types/contracts";

/** Access-token provider, set by the auth layer (M1-05). */
let tokenProvider: () => string | null = () => null;

export function setTokenProvider(fn: () => string | null): void {
  tokenProvider = fn;
}

export class ApiRequestError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

type Mocks = typeof import("./mocks");

/**
 * Answer from the fixtures after a short delay, so loading states are visible.
 * The dynamic import keeps the fixtures out of a normal (non-mock) build.
 */
async function mock<T>(pick: (m: Mocks) => T, ms = 150): Promise<T> {
  const mocks = await import("./mocks");
  await new Promise((resolve) => setTimeout(resolve, ms));
  return pick(mocks);
}

async function request<T>(path: string): Promise<T> {
  const { apiUrl } = getConfig();
  const token = tokenProvider();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${apiUrl}${path}`, { headers });
  if (!res.ok) {
    let code = "INTERNAL";
    let message = res.statusText;
    try {
      const body = await res.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
      }
    } catch {
      // non-JSON error body; keep defaults
    }
    throw new ApiRequestError(code, message, res.status);
  }
  return (await res.json()) as T;
}

// ---- read routes (§7.3, §7.4) ----------------------------------------------

export function getHome(): Promise<HomeResponse> {
  if (USE_MOCKS) return mock((m) => m.home);
  return request<HomeResponse>("/home");
}

export function getGenres(): Promise<GenresResponse> {
  if (USE_MOCKS) return mock((m) => m.genres);
  return request<GenresResponse>("/genres");
}

export function getShows(genre: GenreId, limit = 20): Promise<ShowsResponse> {
  if (USE_MOCKS) return mock((m) => m.shows(genre, limit));
  return request<ShowsResponse>(`/shows?genre=${encodeURIComponent(genre)}&limit=${limit}`);
}

export function getShowDetail(showId: string): Promise<ShowDetailResponse> {
  if (USE_MOCKS) return mock((m) => m.showDetail(showId));
  return request<ShowDetailResponse>(`/shows/${encodeURIComponent(showId)}`);
}

export function getTrending(limit = 10): Promise<TrendingResponse> {
  if (USE_MOCKS) return mock((m) => ({ ...m.trending, items: m.trending.items.slice(0, limit) }));
  return request<TrendingResponse>(`/trending?limit=${limit}`);
}

export function getProgress(episodeId: string): Promise<ProgressResponse> {
  if (USE_MOCKS) return mock((m) => m.progress(episodeId));
  return request<ProgressResponse>(`/progress/${encodeURIComponent(episodeId)}`);
}
