import { useState, useRef, useEffect, useCallback } from 'react';

export interface AudioPlayerState {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isLoading: boolean;
  isBuffering: boolean;
  error: string | null;
}

export interface AudioPlayerControls {
  play: () => void;
  pause: () => void;
  toggle: () => void;
  seek: (time: number) => void;
  setVolume: (vol: number) => void;
  fadeOut: (durationSecs: number) => () => void;
  skipForward: (secs?: number) => void;
  skipBack: (secs?: number) => void;
}

const DEFAULT_STATE: AudioPlayerState = {
  isPlaying: false,
  currentTime: 0,
  duration: 0,
  volume: 1,
  isLoading: false,
  isBuffering: false,
  error: null,
};

export function useAudioPlayer(
  src: string | null,
  options: {
    title?: string;
    artist?: string;
    album?: string;
    autoPlay?: boolean;
    onEnded?: () => void;
  } = {}
): AudioPlayerState & AudioPlayerControls {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fadeTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [state, setState] = useState<AudioPlayerState>(DEFAULT_STATE);

  // Tear down previous audio element
  const destroyAudio = useCallback(() => {
    if (fadeTimerRef.current) {
      clearInterval(fadeTimerRef.current);
      fadeTimerRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!src) {
      destroyAudio();
      setState(DEFAULT_STATE);
      return;
    }

    destroyAudio();
    setState(prev => ({ ...DEFAULT_STATE, volume: prev.volume, isLoading: true }));

    const audio = new Audio();
    audio.preload = 'auto';
    // Enable background audio on iOS
    audio.setAttribute('playsinline', '');
    audioRef.current = audio;

    const onLoadStart   = () => setState(s => ({ ...s, isLoading: true,  error: null }));
    const onCanPlay     = () => setState(s => ({ ...s, isLoading: false }));
    const onLoadedMeta  = () => setState(s => ({ ...s, duration: audio.duration, isLoading: false }));
    const onTimeUpdate  = () => setState(s => ({ ...s, currentTime: audio.currentTime }));
    const onWaiting     = () => setState(s => ({ ...s, isBuffering: true }));
    const onPlaying     = () => setState(s => ({ ...s, isPlaying: true, isBuffering: false }));
    const onPause       = () => setState(s => ({ ...s, isPlaying: false }));
    const onVolumeChange = () => setState(s => ({ ...s, volume: audio.volume }));
    const onEnded = () => {
      setState(s => ({ ...s, isPlaying: false, currentTime: 0 }));
      options.onEnded?.();
    };
    const onError = () => {
      const err = audio.error;
      let msg = 'Audio failed to load';
      if (err) {
        if (err.code === MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED) msg = 'Format not supported — offline playback may be unavailable';
        else if (err.code === MediaError.MEDIA_ERR_NETWORK) msg = 'Network error — check your connection';
      }
      setState(s => ({ ...s, error: msg, isLoading: false, isBuffering: false }));
    };

    audio.addEventListener('loadstart',    onLoadStart);
    audio.addEventListener('canplay',      onCanPlay);
    audio.addEventListener('loadedmetadata', onLoadedMeta);
    audio.addEventListener('timeupdate',   onTimeUpdate);
    audio.addEventListener('waiting',      onWaiting);
    audio.addEventListener('playing',      onPlaying);
    audio.addEventListener('pause',        onPause);
    audio.addEventListener('volumechange', onVolumeChange);
    audio.addEventListener('ended',        onEnded);
    audio.addEventListener('error',        onError);

    // Media Session API — lock screen / Now Playing controls
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title:  options.title  ?? 'Meditation Session',
        artist: options.artist ?? 'Calm',
        album:  options.album  ?? 'Guided Sessions',
      });
      navigator.mediaSession.setActionHandler('play',         () => audio.play().catch(() => null));
      navigator.mediaSession.setActionHandler('pause',        () => audio.pause());
      navigator.mediaSession.setActionHandler('seekbackward', () => { audio.currentTime = Math.max(0, audio.currentTime - 10); });
      navigator.mediaSession.setActionHandler('seekforward',  () => { audio.currentTime = Math.min(audio.duration, audio.currentTime + 10); });
      navigator.mediaSession.setActionHandler('seekto',       (e) => { if (e.seekTime !== undefined) audio.currentTime = e.seekTime; });
    }

    audio.src = src;
    audio.load();
    audio.volume = state.volume;

    if (options.autoPlay) {
      audio.play().catch(() => null); // browsers may block autoplay
    }

    return () => {
      audio.removeEventListener('loadstart',    onLoadStart);
      audio.removeEventListener('canplay',      onCanPlay);
      audio.removeEventListener('loadedmetadata', onLoadedMeta);
      audio.removeEventListener('timeupdate',   onTimeUpdate);
      audio.removeEventListener('waiting',      onWaiting);
      audio.removeEventListener('playing',      onPlaying);
      audio.removeEventListener('pause',        onPause);
      audio.removeEventListener('volumechange', onVolumeChange);
      audio.removeEventListener('ended',        onEnded);
      audio.removeEventListener('error',        onError);
      audio.pause();
      audio.src = '';
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

  const play = useCallback(() => {
    audioRef.current?.play().catch(() => null);
  }, []);

  const pause = useCallback(() => {
    audioRef.current?.pause();
  }, []);

  const toggle = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) audio.play().catch(() => null);
    else audio.pause();
  }, []);

  const seek = useCallback((time: number) => {
    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = Math.max(0, Math.min(audio.duration || 0, time));
      // Update Media Session position
      if ('mediaSession' in navigator && navigator.mediaSession.setPositionState) {
        navigator.mediaSession.setPositionState({
          duration: audio.duration || 0,
          position: audio.currentTime,
          playbackRate: audio.playbackRate,
        });
      }
    }
  }, []);

  const setVolume = useCallback((vol: number) => {
    const audio = audioRef.current;
    if (audio) {
      audio.volume = Math.max(0, Math.min(1, vol));
    }
  }, []);

  /** Smoothly fade audio to 0 over `durationSecs` seconds, then pause. Returns a cancel fn. */
  const fadeOut = useCallback((durationSecs: number = 30): () => void => {
    const audio = audioRef.current;
    if (!audio) return () => null;
    if (fadeTimerRef.current) clearInterval(fadeTimerRef.current);

    const startVol = audio.volume;
    const ticks    = durationSecs * 10; // 100ms intervals
    const step     = startVol / ticks;
    let  elapsed   = 0;

    fadeTimerRef.current = setInterval(() => {
      if (!audioRef.current) { clearInterval(fadeTimerRef.current!); return; }
      elapsed++;
      const newVol = Math.max(0, startVol - step * elapsed);
      audioRef.current.volume = newVol;
      if (newVol <= 0) {
        audioRef.current.pause();
        clearInterval(fadeTimerRef.current!);
        fadeTimerRef.current = null;
      }
    }, 100);

    return () => {
      if (fadeTimerRef.current) {
        clearInterval(fadeTimerRef.current);
        fadeTimerRef.current = null;
      }
    };
  }, []);

  const skipForward = useCallback((secs = 10) => {
    const audio = audioRef.current;
    if (audio) audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + secs);
  }, []);

  const skipBack = useCallback((secs = 10) => {
    const audio = audioRef.current;
    if (audio) audio.currentTime = Math.max(0, audio.currentTime - secs);
  }, []);

  return { ...state, play, pause, toggle, seek, setVolume, fadeOut, skipForward, skipBack };
}

/** Format seconds → M:SS */
export function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}
