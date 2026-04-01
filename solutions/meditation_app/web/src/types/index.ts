export type Screen =
  | 'onboarding'
  | 'home'
  | 'session'
  | 'sleep-story'
  | 'breathing'
  | 'mood'
  | 'streak'
  | 'settings';

export type ExperienceLevel = 'beginner' | 'intermediate' | 'advanced';

export type SessionCategory = 'meditation' | 'sleep' | 'breathing' | 'focus';

export interface Session {
  id: string;
  title: string;
  description: string;
  duration: number; // seconds
  category: SessionCategory;
  instructor: string;
  audioUrl: string;
  gradientStart: string;
  gradientEnd: string;
  isDownloaded: boolean;
  isPremium: boolean;
  plays: number;
}

export interface MoodEntry {
  id: string;
  emoji: string;
  label: string;
  score: number; // 1–5
  note?: string;
  timestamp: string; // ISO string
}

export interface UserProfile {
  name: string;
  goals: string[];
  experienceLevel: ExperienceLevel;
  scheduleDays: number[]; // 0=Sun … 6=Sat
  scheduleTime: string; // "HH:MM"
  onboardingComplete: boolean;
  subscriptionTier: 'free' | 'premium' | 'family';
  reminderEnabled: boolean;
}

export interface StreakData {
  currentStreak: number;
  longestStreak: number;
  totalSessions: number;
  completedDays: string[]; // ISO date strings "YYYY-MM-DD"
}

export interface DownloadedSession {
  sessionId: string;
  downloadedAt: string;
  localUrl: string; // object URL or cached URL
}

export interface AppState {
  user: UserProfile;
  streak: StreakData;
  recentMood: MoodEntry | null;
  downloads: DownloadedSession[];
  currentSession: Session | null;
}
