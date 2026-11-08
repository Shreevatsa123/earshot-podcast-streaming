// Mock data source (CONTEXT §12 "Mocks first").
//
// In mock mode the app serves the committed fixtures from contracts/samples/ instead
// of calling a live API. The fixtures are imported directly so contracts/samples/
// stays the single source of truth (no copied files to drift). Vite bundles the JSON;
// vite.config.ts allows reading from ../contracts via server.fs.allow.

import homeJson from "../../../contracts/samples/home.json";
import showsJson from "../../../contracts/samples/shows.json";
import showDetailJson from "../../../contracts/samples/show_detail.json";
import trendingJson from "../../../contracts/samples/trending.json";
import progressJson from "../../../contracts/samples/progress.json";

import type {
  GenresResponse,
  HomeResponse,
  ProgressResponse,
  ShowDetailResponse,
  ShowsResponse,
  TrendingResponse,
} from "../types/contracts";

export const mockHome = homeJson as unknown as HomeResponse;
export const mockShows = showsJson as unknown as ShowsResponse;
export const mockShowDetail = showDetailJson as unknown as ShowDetailResponse;
export const mockTrending = trendingJson as unknown as TrendingResponse;
export const mockProgress = progressJson as unknown as ProgressResponse;

// §8.3 fixed genres. GET /genres has no committed fixture, so it is defined here.
export const mockGenres: GenresResponse = {
  genres: [
    { id: "true-crime", name: "True Crime" },
    { id: "comedy", name: "Comedy" },
    { id: "news", name: "News" },
    { id: "technology", name: "Technology" },
    { id: "business", name: "Business" },
    { id: "science", name: "Science" },
    { id: "sports", name: "Sports" },
    { id: "history", name: "History" },
  ],
};
