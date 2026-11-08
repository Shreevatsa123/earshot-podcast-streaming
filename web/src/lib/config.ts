// Runtime config loader (CONTEXT §9 "Web runtime config").
//
// The app fetches /config.json at startup instead of baking stage values into the
// bundle, so one build runs in every stage. In production the Web construct (M1-04)
// deploys config.json to the web bucket. Locally, web/public/config.json is served.

export interface RuntimeConfig {
  apiUrl: string;
  region: string;
  userPoolId: string;
  webClientId: string;
  cognitoDomain: string;
  stage: string;
}

/** True when the app should serve committed fixtures instead of a live API. */
export const USE_MOCKS: boolean = import.meta.env.VITE_USE_MOCKS === "true";

let cached: RuntimeConfig | null = null;

const EMPTY_CONFIG: RuntimeConfig = {
  apiUrl: "",
  region: "us-east-1",
  userPoolId: "",
  webClientId: "",
  cognitoDomain: "",
  stage: "local",
};

/**
 * Load /config.json once and cache it. In mock mode a missing or empty config is
 * fine, so failures fall back to EMPTY_CONFIG rather than crashing the app.
 */
export async function loadConfig(): Promise<RuntimeConfig> {
  if (cached) return cached;
  try {
    const res = await fetch("/config.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`config.json ${res.status}`);
    const data = (await res.json()) as Partial<RuntimeConfig>;
    cached = { ...EMPTY_CONFIG, ...data };
  } catch (err) {
    if (!USE_MOCKS) {
      // Outside mock mode a real config is required; surface the problem.
      console.error("Failed to load /config.json", err);
    }
    cached = { ...EMPTY_CONFIG };
  }
  return cached;
}

export function getConfig(): RuntimeConfig {
  if (!cached) {
    throw new Error("Config not loaded yet. Call loadConfig() before getConfig().");
  }
  return cached;
}
