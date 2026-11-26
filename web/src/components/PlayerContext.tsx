import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { EpisodeCard } from "../types/contracts";

/**
 * Now-playing state shared by every page, backed by one HTML5 <audio> element.
 *
 * Audio streams straight from the publisher's `audio_url` (CONTEXT §1). When a card
 * carries `position_sec` (Continue Listening), playback starts there.
 * Still to come: resume via GET /progress/{id} for every episode (M1-07) and the
 * playback event emitter (M1-08).
 */
export const PLAYBACK_RATES = [0.8, 1, 1.25, 1.5, 2] as const;

interface PlayerState {
  current: EpisodeCard | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  playbackRate: number;
  error: string | null;
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

  const startPlayback = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.play().catch(() => {
      // Autoplay blocked or the publisher URL failed; the error handler covers the latter.
      setIsPlaying(false);
    });
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
      const start = episode.position_sec ?? 0;
      // Start from the beginning if the saved position is in the last 15 seconds.
      startAtRef.current = start >= episode.duration_sec - 15 ? 0 : start;
      setCurrent(episode);
      setError(null);
      setCurrentTime(startAtRef.current);
      setMediaDuration(0);
      audio.src = episode.audio_url;
      audio.playbackRate = playbackRate;
      startPlayback();
    },
    [current, playbackRate, startPlayback],
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
  }, []);

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
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
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
