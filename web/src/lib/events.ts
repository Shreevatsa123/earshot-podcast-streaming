// Playback events: build them per CONTEXT §6 and send them to POST /events (§7.5). M1-08.
//
// Emission rules (§6), applied by the player (PlayerContext.tsx) with this sender:
// - play on start/resume, pause, seek after it completes, buffer on `waiting`,
//   heartbeat every 15 s while playing, complete on `ended`
// - batches of up to 25; flush every 5 s, and right away on pause, complete and page hide
//   (page hide uses fetch keepalive so the request outlives the page)
// - retry events rejected as THROTTLED, at most 3 times, with exponential backoff.
//   Network errors, 429 and 5xx are retried the same way: every event has a unique
//   event_id, and the backend never double-counts one (§6), so a resend is safe.
//
// The client never sends user_id or server_ts: ingest sets both (§6, §7.2).

import { currentAccessToken } from "./api";
import { getConfig, USE_MOCKS } from "./config";
import { getRegion } from "./region";
import type { EpisodeCard, GenreId } from "../types/contracts";

export type EventType = "play" | "pause" | "seek" | "buffer" | "heartbeat" | "complete";

export interface PlaybackEvent {
  event_id: string;
  schema_version: 1;
  session_id: string;
  show_id: string;
  episode_id: string;
  genre: GenreId;
  event_type: EventType;
  position_sec: number;
  duration_sec: number;
  client_ts: number;
  region: string;
  device: "web";
}

/** One continuous listening session of one episode (§6 `session_id`). */
export interface Track {
  episode: EpisodeCard;
  sessionId: string;
}

export const BATCH_SIZE = 25;
export const FLUSH_MS = 5_000;
export const HEARTBEAT_MS = 15_000;
export const MAX_RETRIES = 3;
const MAX_POSITION_SEC = 86_400;
const SEND_RIGHT_AWAY: ReadonlySet<EventType> = new Set(["pause", "complete"]);

/** A random UUID v4 (event_id and session_id must be v4, §6). */
export function uuid4(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function newTrack(episode: EpisodeCard): Track {
  return { episode, sessionId: uuid4() };
}

/** Build one §6 event. Positions are whole seconds after the action, clamped to 0–86400. */
export function makeEvent(track: Track, type: EventType, positionSec: number, now = Date.now()): PlaybackEvent {
  const { episode } = track;
  const position = Number.isFinite(positionSec) ? Math.floor(positionSec) : 0;
  return {
    event_id: uuid4(),
    schema_version: 1,
    session_id: track.sessionId,
    show_id: episode.show_id,
    episode_id: episode.episode_id,
    genre: episode.genre,
    event_type: type,
    position_sec: Math.min(MAX_POSITION_SEC, Math.max(0, position)),
    duration_sec: Math.max(1, Math.round(episode.duration_sec)),
    client_ts: now,
    region: getRegion(),
    device: "web",
  };
}

interface Queued {
  event: PlaybackEvent;
  attempts: number;
}

interface IngestResponse {
  accepted: number;
  rejected: { index: number; reason: string }[];
}

/** Counters for debugging (shown in the console in mock mode). */
export const eventStats = { queued: 0, sent: 0, accepted: 0, rejected: 0, retried: 0, dropped: 0 };

class EventSender {
  private queue: Queued[] = [];
  private timer: number | undefined;

  /** Queue an event; pause and complete go out right away, the rest within 5 s. */
  emit(event: PlaybackEvent): void {
    this.queue.push({ event, attempts: 0 });
    eventStats.queued++;
    if (SEND_RIGHT_AWAY.has(event.event_type) || this.queue.length >= BATCH_SIZE) void this.flush();
    else this.schedule();
  }

  /** Send everything queued, in batches of 25. `keepalive` for page hide. */
  async flush({ keepalive = false }: { keepalive?: boolean } = {}): Promise<void> {
    window.clearTimeout(this.timer);
    this.timer = undefined;
    const sends: Promise<void>[] = [];
    while (this.queue.length > 0) sends.push(this.send(this.queue.splice(0, BATCH_SIZE), keepalive));
    await Promise.all(sends);
  }

  private schedule(): void {
    if (this.timer !== undefined) return;
    this.timer = window.setTimeout(() => {
      this.timer = undefined;
      void this.flush();
    }, FLUSH_MS);
  }

  private retryLater(items: Queued[]): void {
    for (const item of items) {
      if (item.attempts >= MAX_RETRIES) {
        eventStats.dropped++;
        continue;
      }
      item.attempts++;
      eventStats.retried++;
      // 500 ms, 1 s, 2 s (+ up to 250 ms jitter so many tabs don't retry in step)
      const delay = 250 * 2 ** item.attempts + Math.random() * 250;
      window.setTimeout(() => {
        this.queue.push(item);
        this.schedule();
      }, delay);
    }
  }

  private async send(batch: Queued[], keepalive: boolean): Promise<void> {
    eventStats.sent += batch.length;
    const body = JSON.stringify({ events: batch.map((q) => q.event) });

    if (USE_MOCKS) {
      eventStats.accepted += batch.length;
      console.debug(`[earshot events] mock send of ${batch.length}:`, batch.map((q) => q.event.event_type).join(", "));
      return;
    }
    const token = currentAccessToken();
    if (!token) {
      eventStats.dropped += batch.length; // logged out: nothing can be sent for this user
      return;
    }

    let res: Response;
    try {
      res = await fetch(`${getConfig().apiUrl}/events`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body,
        keepalive,
      });
    } catch {
      this.retryLater(batch); // offline or the request was cut off
      return;
    }

    if (res.status === 202) {
      let result: IngestResponse | null = null;
      try {
        result = (await res.json()) as IngestResponse;
      } catch {
        // a 202 without a readable body still means the events were taken
      }
      const rejected = result?.rejected ?? [];
      eventStats.accepted += batch.length - rejected.length;
      const throttled: Queued[] = [];
      for (const { index, reason } of rejected) {
        const item = batch[index];
        if (!item) continue;
        if (reason === "THROTTLED") throttled.push(item);
        else {
          eventStats.rejected++;
          console.warn(`[earshot events] ${item.event.event_type} rejected: ${reason}`);
        }
      }
      this.retryLater(throttled);
      return;
    }
    if (res.status === 429 || res.status >= 500) {
      this.retryLater(batch);
      return;
    }
    // 400 (bad body), 401 (token), 403: resending the same request won't help.
    eventStats.dropped += batch.length;
    console.warn(`[earshot events] POST /events answered ${res.status}; ${batch.length} events dropped`);
  }
}

export const events = new EventSender();
