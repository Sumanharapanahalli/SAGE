import { useState, useCallback } from 'react';
import type { AppState, UserProfile, MoodEntry, StreakData, DownloadedSession } from '../types';

const STORAGE_KEY = 'calm_app_state';

function todayISO(): string {
  return new Date().toISOString().split('T')[0];
}

function buildDefaultStreak(): StreakData {
  // Seed some history for demo purposes
  const days: string[] = [];
  const today = new Date();
  for (let i = 30; i >= 0; i--) {
    if (Math.random() > 0.35 || i < 7) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      days.push(d.toISOString().split('T')[0]);
    }
  }
  return { currentStreak: 7, longestStreak: 14, totalSessions: days.length, completedDays: days };
}

function loadState(): AppState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as AppState;
      return parsed;
    }
  } catch {
    // ignore parse errors
  }
  return {
    user: {
      name: '',
      goals: [],
      experienceLevel: 'beginner',
      scheduleDays: [1, 3, 5],
      scheduleTime: '08:00',
      onboardingComplete: false,
      subscriptionTier: 'free',
      reminderEnabled: true,
    },
    streak: buildDefaultStreak(),
    recentMood: null,
    downloads: [],
    currentSession: null,
  };
}

function saveState(state: AppState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // ignore quota errors
  }
}

export function useAppState() {
  const [state, setState] = useState<AppState>(loadState);

  const updateState = useCallback((updater: (prev: AppState) => AppState) => {
    setState(prev => {
      const next = updater(prev);
      saveState(next);
      return next;
    });
  }, []);

  const completeOnboarding = useCallback((profile: Partial<UserProfile>) => {
    updateState(prev => ({
      ...prev,
      user: { ...prev.user, ...profile, onboardingComplete: true },
    }));
  }, [updateState]);

  const logMood = useCallback((entry: Omit<MoodEntry, 'id' | 'timestamp'>) => {
    const full: MoodEntry = {
      ...entry,
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
    };
    updateState(prev => ({ ...prev, recentMood: full }));
    return full;
  }, [updateState]);

  const markSessionComplete = useCallback(() => {
    updateState(prev => {
      const today = todayISO();
      const alreadyDone = prev.streak.completedDays.includes(today);
      if (alreadyDone) return prev;

      const days = [...prev.streak.completedDays, today].sort();
      // Recalculate current streak
      let streak = 0;
      const d = new Date();
      while (true) {
        const iso = d.toISOString().split('T')[0];
        if (days.includes(iso)) { streak++; d.setDate(d.getDate() - 1); }
        else break;
      }
      return {
        ...prev,
        streak: {
          completedDays: days,
          currentStreak: streak,
          longestStreak: Math.max(prev.streak.longestStreak, streak),
          totalSessions: prev.streak.totalSessions + 1,
        },
      };
    });
  }, [updateState]);

  const updateDownloads = useCallback((dl: DownloadedSession) => {
    updateState(prev => ({
      ...prev,
      downloads: [...prev.downloads.filter(d => d.sessionId !== dl.sessionId), dl],
    }));
  }, [updateState]);

  const isDownloaded = useCallback((sessionId: string): boolean => {
    return state.downloads.some(d => d.sessionId === sessionId);
  }, [state.downloads]);

  const getLocalUrl = useCallback((sessionId: string, fallback: string): string => {
    const dl = state.downloads.find(d => d.sessionId === sessionId);
    return dl?.localUrl ?? fallback;
  }, [state.downloads]);

  const updateUser = useCallback((updates: Partial<UserProfile>) => {
    updateState(prev => ({ ...prev, user: { ...prev.user, ...updates } }));
  }, [updateState]);

  return {
    state,
    completeOnboarding,
    logMood,
    markSessionComplete,
    updateDownloads,
    isDownloaded,
    getLocalUrl,
    updateUser,
  };
}
