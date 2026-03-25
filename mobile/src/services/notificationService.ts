/**
 * Firebase Cloud Messaging service.
 * Handles token management, foreground / background / quit-state notifications.
 * Fall alerts must surface within 20s of event — FCM high-priority + critical alerts on iOS.
 */
import messaging, { FirebaseMessagingTypes } from '@react-native-firebase/messaging';
import { Platform, Alert } from 'react-native';
import { ALERT_CHANNEL_ID, ALERT_CHANNEL_NAME } from '../constants';
import { registerFCMToken, unregisterFCMToken } from './api';

export type AlertNotificationPayload = {
  alertId: string;
  patientName: string;
  severity: string;
  timestamp: string;
};

type AlertHandler = (payload: AlertNotificationPayload) => void;

let foregroundAlertHandler: AlertHandler | null = null;

// ---------------------------------------------------------------------------
// Initialise — call once from App.tsx on mount
// ---------------------------------------------------------------------------

export async function initNotifications(): Promise<void> {
  // iOS: request permission including criticalAlert for HIPAA overrides
  if (Platform.OS === 'ios') {
    const authStatus = await messaging().requestPermission({
      alert: true,
      announcement: false,
      badge: true,
      carPlay: false,
      criticalAlert: true,
      provisional: false,
      sound: true,
    });
    const granted =
      authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
      authStatus === messaging.AuthorizationStatus.PROVISIONAL;
    if (!granted) {
      console.warn('[FCM] Notification permission denied');
      return;
    }
  }

  // Android: create high-priority channel (required for Android 8+)
  if (Platform.OS === 'android') {
    const notifee = await getNotifee();
    if (notifee) {
      await notifee.createChannel({
        id: ALERT_CHANNEL_ID,
        name: ALERT_CHANNEL_NAME,
        importance: notifee.AndroidImportance.HIGH,
        vibration: true,
        lights: true,
        lightColor: notifee.AndroidColor.RED,
        sound: 'default',
      });
    }
  }

  // Register / refresh FCM token
  await refreshFCMToken();

  // Token refresh listener
  messaging().onTokenRefresh(async (newToken) => {
    await registerFCMToken(newToken, Platform.OS as 'ios' | 'android');
  });

  // Foreground message handler
  messaging().onMessage(async (remoteMessage) => {
    handleIncomingMessage(remoteMessage, 'foreground');
  });

  // Background / quit — tap brings app to front
  messaging().onNotificationOpenedApp((remoteMessage) => {
    handleIncomingMessage(remoteMessage, 'background');
  });

  // App opened from quit state
  const initialMessage = await messaging().getInitialNotification();
  if (initialMessage) {
    handleIncomingMessage(initialMessage, 'quit');
  }
}

// ---------------------------------------------------------------------------
// FCM token
// ---------------------------------------------------------------------------

export async function refreshFCMToken(): Promise<string | null> {
  try {
    const token = await messaging().getToken();
    await registerFCMToken(token, Platform.OS as 'ios' | 'android');
    return token;
  } catch (err) {
    console.error('[FCM] Token registration failed', err);
    return null;
  }
}

export async function revokeFCMToken(): Promise<void> {
  try {
    const token = await messaging().getToken();
    await unregisterFCMToken(token);
    await messaging().deleteToken();
  } catch (err) {
    console.error('[FCM] Token revocation failed', err);
  }
}

// ---------------------------------------------------------------------------
// Message handler
// ---------------------------------------------------------------------------

function parseAlertPayload(
  data: FirebaseMessagingTypes.RemoteMessage['data']
): AlertNotificationPayload | null {
  if (!data?.alertId) return null;
  return {
    alertId: data.alertId as string,
    patientName: (data.patientName as string) ?? 'Unknown',
    severity: (data.severity as string) ?? 'unknown',
    timestamp: (data.timestamp as string) ?? new Date().toISOString(),
  };
}

function handleIncomingMessage(
  message: FirebaseMessagingTypes.RemoteMessage,
  state: 'foreground' | 'background' | 'quit'
): void {
  const payload = parseAlertPayload(message.data);
  if (!payload) return;

  console.info(`[FCM] Fall alert received (${state}): alertId=${payload.alertId}`);

  if (state === 'foreground' && foregroundAlertHandler) {
    foregroundAlertHandler(payload);
  }
}

// ---------------------------------------------------------------------------
// Register a foreground alert handler (AlertDashboard calls this)
// ---------------------------------------------------------------------------

export function setForegroundAlertHandler(handler: AlertHandler): () => void {
  foregroundAlertHandler = handler;
  return () => {
    foregroundAlertHandler = null;
  };
}

// ---------------------------------------------------------------------------
// Notifee lazy import (optional — used only for Android channels)
// ---------------------------------------------------------------------------

async function getNotifee(): Promise<any | null> {
  try {
    const mod = await import('@notifee/react-native');
    return mod.default;
  } catch {
    return null;
  }
}
