import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { EpisodeCard } from "../types/contracts";
import { getProgress } from "../lib/api";
import { formatDuration } from "../lib/format";
import { startFrom, startFromProgress } from "../lib/resume";
import { events, HEARTBEAT_MS, makeEvent, newTrack } from "../lib/events";
import type { EventType, Track } from "../lib/events";

/**
 * Now-playing state shared by every page, backed by one HTML5 <audio> element.
 *
 * Audio streams straight from the publisher's `audio_url` (CONTEXT §1).
 * Resume (M1-07): playback starts at once (at the card's `position_sec`, if any), then
 * GET /progress/{id} says where this user really stopped, from any device, and the
 * player jumps there. Positions near the end or marked completed start over.
 * Events (M1-08): play, pause, seek, buffer, a heartbeat every 15 s and complete go to
 * POST /events through lib/events.ts, which batches and retries them (§6).
 */
export const PLAYBACK_RATES = [0.8, 1, 1.25, 1.5, 2] as const;

/** How long to wait for GET /progress before giving up and keeping the first guess. */
const PROGRESS_TIMEOUT_MS = 2500;
const NOTICE_MS = 4000;

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error("timeout")), ms);
    promise.then(
      (value) => {
        window.clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        window.clearTimeout(timer);
        reject(err);
      },
    );
  });
}

interface PlayerState {
  current: EpisodeCard | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  playbackRate: number;
  error: string | null;
  notice: string | null;
  /** Play `episode`; if it's already loaded, toggle play/pause instead. */
  play: (episode: EpisodeCard) => void;
  togglePlayPause: () => void;
  seek: (timeSec: number) => void;
  skip: (deltaSec: number) => void;
  setVolume: (volume: number) => void;
  toggleMute: () => void;
  cyclePlaybackRate: () => void;
  close: () => void;
}

const PlayerContext = createContext<PlayerState | null>(null);

export function PlayerProvider({ children }: { children: ReactNode }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const startAtRef = useRef(0);
  const [current, setCurrent] = useState<EpisodeCard | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [mediaDuration, setMediaDuration] = useState(0);
  const [volume, setVolumeState] = useState(0.8);
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [error, setError] = useState<string | null>(null);
  /** Short message for the player bar, e.g. "Resumed at 9:38". Clears itself. */
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), NOTICE_MS);
    return () => window.clearTimeout(timer);
  }, [notice]);

  // ---- playback events (M1-08) ------------------------------------------------
  /** The episode being listened to and its session id (§6); null when nothing's loaded. */
  const trackRef = useRef<Track | null>(null);
  /** Set when we've already reported a pause the browser is about to fire again. */
  const suppressPauseRef = useRef(false);
  const heartbeatRef = useRef<number | undefined>(undefined);

  const emit = useCallback((type: EventType, positionSec?: number) => {
    const track = trackRef.current;
    if (!track) return;
    events.emit(makeEvent(track, type, positionSec ?? audioRef.current?.currentTime ?? 0));
  }, []);

  const stopHeartbeat = useCallback(() => {
    window.clearInterval(heartbeatRef.current);
    heartbeatRef.current = undefined;
  }, []);

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatRef.current = window.setInterval(() => {
      if (audioRef.current && !audioRef.current.paused) emit("heartbeat");
    }, HEARTBEAT_MS);
  }, [emit, stopHeartbeat]);

  /** Report a pause for the current episode now, and skip the browser's own pause event. */
  const reportPauseNow = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !trackRef.current || audio.paused) return;
    emit("pause");
    suppressPauseRef.current = true;
  }, [emit]);

  // Send whatever is queued when the page is hidden or closed (keepalive, §6).
  useEffect(() => {
    const flushNow = () => void events.flush({ keepalive: true });
    const onVisibility = () => {
      if (document.visibilityState === "hidden") flushNow();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", flushNow);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("pagehide", flushNow);
    };
  }, []);

  useEffect(() => stopHeartbeat, [stopHeartbeat]);

  const startPlayback = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.play().catch(() => {
      // Autoplay blocked or the publisher URL failed; the error handler covers the latter.
      setIsPlaying(false);
    });
  }, []);

  // Each play() of a new episode gets an id, so a late /progress answer for an episode
  // the user already left is ignored.
  const loadIdRef = useRef(0);
  const userSeekedRef = useRef(false);

  /** Jump to `target` now if the audio is loaded, or as soon as its metadata arrives. */
  const applyStart = useCallback((target: number) => {
    startAtRef.current = target;
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.readyState >= HTMLMediaElement.HAVE_METADATA) {
      if (Math.abs(audio.currentTime - target) > 1) audio.currentTime = target;
    } else {
      setCurrentTime(target);
    }
  }, []);

  const play = useCallback(
    (episode: EpisodeCard) => {
      const audio = audioRef.current;
      if (!audio) return;
      if (current?.episode_id === episode.episode_id) {
        if (audio.paused) startPlayback();
        else audio.pause();
        return;
      }
      const loadId = ++loadIdRef.current;
      userSeekedRef.current = false;
      reportPauseNow(); // the episode we're leaving
      trackRef.current = newTrack(episode); // new listening session (§6 session_id)
      // First guess: the position on the card (Continue Listening rows carry one).
      startAtRef.current = startFrom(episode.position_sec ?? 0, episode.duration_sec);
      setCurrent(episode);
      setError(null);
      setNotice(null);
      setCurrentTime(startAtRef.current);
      setMediaDuration(0);
      audio.src = episode.audio_url;
      audio.playbackRate = playbackRate;
      // Start right away, inside the click: browsers may block play() after an await.
      startPlayback();

      // Then ask the API where this user stopped (works across devices) and jump there.
      withTimeout(getProgress(episode.episode_id), PROGRESS_TIMEOUT_MS)
        .then((progress) => {
          if (loadIdRef.current !== loadId || userSeekedRef.current) return;
          const target = startFromProgress(progress, episode.duration_sec);
          if (target === null) return; // nothing saved: keep the card's guess
          applyStart(target);
          if (target > 0) setNotice(`Resumed at ${formatDuration(target)}`);
        })
        .catch(() => {
          // No answer in time or an API error: keep the card's guess, playback goes on.
        });
    },
    [current, playbackRate, startPlayback, applyStart, reportPauseNow],
  );

  const togglePlayPause = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !current) return;
    if (audio.paused) startPlayback();
    else audio.pause();
  }, [current, startPlayback]);

  const duration = mediaDuration || current?.duration_sec || 0;

  const seek = useCallback(
    (timeSec: number) => {
      const audio = audioRef.current;
      if (!audio || !current) return;
      const clamped = Math.max(0, Math.min(duration || timeSec, timeSec));
      userSeekedRef.current = true;
      audio.currentTime = clamped;
      setCurrentTime(clamped);
    },
    [current, duration],
  );

  const skip = useCallback(
    (deltaSec: number) => seek((audioRef.current?.currentTime ?? 0) + deltaSec),
    [seek],
  );

  const setVolume = useCallback((v: number) => {
    const clamped = Math.max(0, Math.min(1, v));
    setVolumeState(clamped);
    setIsMuted(clamped === 0);
  }, []);

  const toggleMute = useCallback(() => setIsMuted((m) => !m), []);

  const cyclePlaybackRate = useCallback(() => {
    setPlaybackRate((rate) => {
      const idx = PLAYBACK_RATES.indexOf(rate as (typeof PLAYBACK_RATES)[number]);
      return PLAYBACK_RATES[(idx + 1) % PLAYBACK_RATES.length];
    });
  }, []);

  const close = useCallback(() => {
    reportPauseNow();
    trackRef.current = null;
    stopHeartbeat();
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    }
    setCurrent(null);
    setIsPlaying(false);
    setCurrentTime(0);
    setError(null);
  }, [reportPauseNow, stopHeartbeat]);

  // Keep the element in sync with the volume, mute and speed controls.
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = volume;
    audio.muted = isMuted;
    audio.playbackRate = playbackRate;
  }, [volume, isMuted, playbackRate]);

  // Space toggles play/pause, except while typing or on a focused button.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON" || tag === "SELECT") return;
      if (e.code === "Space" && current) {
        e.preventDefault();
        togglePlayPause();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [current, togglePlayPause]);

  const value = useMemo<PlayerState>(
    () => ({
      current,
      isPlaying,
      currentTime,
      duration,
      volume,
      isMuted,
      playbackRate,
      error,
      notice,
      play,
      togglePlayPause,
      seek,
      skip,
      setVolume,
      toggleMute,
      cyclePlaybackRate,
      close,
    }),
    [
      current,
      isPlaying,
      currentTime,
      duration,
      volume,
      isMuted,
      playbackRate,
      error,
      notice,
      play,
      togglePlayPause,
      seek,
      skip,
      setVolume,
      toggleMute,
      cyclePlaybackRate,
      close,
    ],
  );

  return (
    <PlayerContext.Provider value={value}>
      {children}
      <audio
        ref={audioRef}
        preload="metadata"
        onLoadedMetadata={(e) => {
          const audio = e.currentTarget;
          if (Number.isFinite(audio.duration)) setMediaDuration(audio.duration);
          if (startAtRef.current > 0) audio.currentTime = startAtRef.current;
        }}
        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
        onPlay={() => {
          setIsPlaying(true);
          suppressPauseRef.current = false;
          emit("play");
          startHeartbeat();
        }}
        onPause={(e) => {
          setIsPlaying(false);
          stopHeartbeat();
          if (suppressPauseRef.current) {
            suppressPauseRef.current = false; // already reported
            return;
          }
          if (!e.currentTarget.ended) emit("pause"); // at the end, `complete` covers it
        }}
        onSeeked={() => emit("seek")}
        onWaiting={() => emit("buffer")}
        onEnded={(e) => {
          setIsPlaying(false);
          stopHeartbeat();
          const audio = e.currentTarget;
          emit("complete", Number.isFinite(audio.duration) ? audio.duration : audio.currentTime);
        }}
        onError={(e) => {
          if (!e.currentTarget.getAttribute("src")) return;
          setIsPlaying(false);
          setError("This episode couldn't be loaded from the publisher.");
        }}
      />
    </PlayerContext.Provider>
  );
}

export function usePlayer(): PlayerState {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error("usePlayer must be used within a PlayerProvider");
  return ctx;
}
