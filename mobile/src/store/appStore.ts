/**
 * Global state using Zustand with immer middleware.
 * Keeps auth state, active alerts, and device status.
 */
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { FallAlert, DeviceStatus, AuthState, AppSettings } from '../types';
import { AUTO_LOCK_TIMEOUT_MS } from '../constants';

interface AppState {
  auth: AuthState;
  alerts: FallAlert[];
  deviceStatuses: Record<string, DeviceStatus>;
  settings: AppSettings;

  // Actions
  setAuthenticated: (userId: string, accessToken: string, refreshToken: string) => void;
  setLocked: (locked: boolean) => void;
  logout: () => void;
  upsertAlert: (alert: FallAlert) => void;
  removeAlert: (alertId: string) => void;
  setAlerts: (alerts: FallAlert[]) => void;
  updateDeviceStatus: (status: DeviceStatus) => void;
  updateSettings: (partial: Partial<AppSettings>) => void;
}

const DEFAULT_SETTINGS: AppSettings = {
  autoLockTimeout: AUTO_LOCK_TIMEOUT_MS / 1000,
  biometricEnabled: true,
  theme: 'system',
  notifications: {
    fallAlerts: true,
    lowBattery: true,
    deviceOffline: true,
    vibrate: true,
    sound: true,
    criticalAlertsOverride: true,
    quietHoursEnabled: false,
    quietHoursStart: '22:00',
    quietHoursEnd: '07:00',
  },
  mapType: 'standard',
  gpsRefreshInterval: 4,
};

export const useAppStore = create<AppState>()(
  immer((set) => ({
    auth: {
      accessToken: null,
      refreshToken: null,
      userId: null,
      isAuthenticated: false,
      isLocked: false,
    },
    alerts: [],
    deviceStatuses: {},
    settings: DEFAULT_SETTINGS,

    setAuthenticated: (userId, accessToken, refreshToken) =>
      set((state) => {
        state.auth.userId = userId;
        state.auth.accessToken = accessToken;
        state.auth.refreshToken = refreshToken;
        state.auth.isAuthenticated = true;
        state.auth.isLocked = false;
      }),

    setLocked: (locked) =>
      set((state) => {
        state.auth.isLocked = locked;
      }),

    logout: () =>
      set((state) => {
        state.auth = {
          accessToken: null,
          refreshToken: null,
          userId: null,
          isAuthenticated: false,
          isLocked: false,
        };
        state.alerts = [];
        state.deviceStatuses = {};
      }),

    upsertAlert: (alert) =>
      set((state) => {
        const idx = state.alerts.findIndex((a) => a.id === alert.id);
        if (idx >= 0) {
          state.alerts[idx] = alert;
        } else {
          state.alerts.unshift(alert); // newest first
        }
      }),

    removeAlert: (alertId) =>
      set((state) => {
        state.alerts = state.alerts.filter((a) => a.id !== alertId);
      }),

    setAlerts: (alerts) =>
      set((state) => {
        state.alerts = alerts;
      }),

    updateDeviceStatus: (status) =>
      set((state) => {
        state.deviceStatuses[status.deviceId] = status;
      }),

    updateSettings: (partial) =>
      set((state) => {
        Object.assign(state.settings, partial);
      }),
  }))
);
