// The listening region (CONTEXT §6 `region`), picked on the Settings page.
//
// Every playback event carries a region. It's a demo control: switching it lets one
// browser stand in for listeners elsewhere (e.g. to watch per-region QoE alerts). The
// event emitter (M1-08) reads it with `getRegion()`. Stored in localStorage.

import { useSyncExternalStore } from "react";

export const REGIONS = [
  { id: "us-east", name: "US East", note: "Virginia" },
  { id: "us-west", name: "US West", note: "Oregon" },
  { id: "eu-west", name: "Europe West", note: "Ireland" },
  { id: "ap-south", name: "Asia Pacific South", note: "Mumbai" },
] as const;

export type RegionId = (typeof REGIONS)[number]["id"];

const STORAGE_KEY = "earshot.region";
const DEFAULT_REGION: RegionId = "us-east";
const listeners = new Set<() => void>();

function isRegion(value: string | null): value is RegionId {
  return REGIONS.some((r) => r.id === value);
}

export function getRegion(): RegionId {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isRegion(stored) ? stored : DEFAULT_REGION;
  } catch {
    return DEFAULT_REGION;
  }
}

export function setRegion(region: RegionId): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, region);
  } catch {
    // storage unavailable (private mode); the choice lasts until reload
  }
  listeners.forEach((fn) => fn());
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** The current region, re-rendering when it changes. */
export function useRegion(): RegionId {
  return useSyncExternalStore(subscribe, getRegion, () => DEFAULT_REGION);
}
