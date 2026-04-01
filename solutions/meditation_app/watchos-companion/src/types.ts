// ─── Domain Types ────────────────────────────────────────────────────────────

export type Screen = 'glance' | 'quick-start' | 'active' | 'complete';
export type BreathingPreset = 'box' | '4-7-8' | 'wim-hof';
export type SessionPhase = 'inhale' | 'hold' | 'exhale' | 'hold2';
export type MoodRating = 1 | 2 | 3 | 4 | 5;
export type SyncStatus = 'idle' | 'syncing' | 'synced' | 'offline';

// ─── Preset Configuration ────────────────────────────────────────────────────

export interface PhaseConfig {
  phase: SessionPhase;
  label: string;
  duration: number; // seconds
}

export interface PresetConfig {
  id: BreathingPreset;
  name: string;
  tagline: string;
  color: string;
  icon: string;
  phases: PhaseConfig[];
  totalCycles: number;
  estimatedMinutes: number;
}

// ─── Session Data (mirrors HKWorkoutSession output) ──────────────────────────

export interface SessionData {
  id: string;
  presetId: BreathingPreset;
  startTime: number;       // Unix ms — synced via WatchConnectivity
  endTime: number;
  elapsedSeconds: number;
  heartRates: number[];    // Raw HealthKit HKQuantityTypeIdentifierHeartRate samples
  avgHeartRate: number;
  cyclesCompleted: number;
  moodRating: MoodRating | null;
  synced: boolean;
}

// ─── Complication Data (WidgetKit / CLKComplicationDataSource) ───────────────

export interface ComplicationData {
  streak: number;          // CLKSimpleTextProvider text
  lastSessionDate: number; // for "today" detection
  nextRecommended: BreathingPreset;
}

// ─── Preset Registry ─────────────────────────────────────────────────────────

export const PRESETS: Record<BreathingPreset, PresetConfig> = {
  box: {
    id: 'box',
    name: 'Box Breathing',
    tagline: 'Focus & calm',
    color: '#0A84FF',
    icon: '⬜',
    phases: [
      { phase: 'inhale', label: 'Inhale',  duration: 4 },
      { phase: 'hold',   label: 'Hold',    duration: 4 },
      { phase: 'exhale', label: 'Exhale',  duration: 4 },
      { phase: 'hold2',  label: 'Hold',    duration: 4 },
    ],
    totalCycles: 6,
    estimatedMinutes: 6,
  },
  '4-7-8': {
    id: '4-7-8',
    name: '4-7-8 Breathing',
    tagline: 'Relax & sleep',
    color: '#BF5AF2',
    icon: '🌙',
    phases: [
      { phase: 'inhale', label: 'Inhale',  duration: 4 },
      { phase: 'hold',   label: 'Hold',    duration: 7 },
      { phase: 'exhale', label: 'Exhale',  duration: 8 },
    ],
    totalCycles: 4,
    estimatedMinutes: 6,
  },
  'wim-hof': {
    id: 'wim-hof',
    name: 'Wim Hof',
    tagline: 'Energize',
    color: '#FF9F0A',
    icon: '❄️',
    phases: [
      { phase: 'inhale', label: 'Inhale',  duration: 2 },
      { phase: 'exhale', label: 'Exhale',  duration: 1 },
    ],
    totalCycles: 30,
    estimatedMinutes: 5,
  },
};

// ─── localStorage Keys ───────────────────────────────────────────────────────

export const STORAGE = {
  STREAK:   'mindful_streak',
  SESSIONS: 'mindful_sessions',
} as const;
