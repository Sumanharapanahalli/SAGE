/**
 * HIPAA compliance controls:
 *  - Auto-lock after 5min inactivity (AppState + touch tracking)
 *  - Screenshot prevention via FLAG_SECURE (Android) / UIScreen overlay (iOS)
 *  - Biometric re-authentication on unlock
 */
import { AppState, AppStateStatus, Platform } from 'react-native';
import ReactNativeBiometrics, { BiometryTypes } from 'react-native-biometrics';
import { AUTO_LOCK_TIMEOUT_MS } from '../constants';

// ---------------------------------------------------------------------------
// Screenshot prevention
// ---------------------------------------------------------------------------

let screenshotPreventionActive = false;

export async function enableScreenshotPrevention(): Promise<void> {
  if (screenshotPreventionActive) return;
  try {
    if (Platform.OS === 'android') {
      const { NativeModules } = require('react-native');
      // Requires custom native module (FLAG_SECURE) or react-native-prevent-screenshot
      NativeModules.RNPreventScreenshot?.enableSecureView?.();
    } else {
      // iOS: no direct API — use react-native-prevent-screenshot or overlayWindow trick
      const PreventScreenshot = require('react-native-prevent-screenshot').default;
      PreventScreenshot.enabled(true);
    }
    screenshotPreventionActive = true;
  } catch (err) {
    console.warn('[HIPAA] Screenshot prevention not available:', err);
  }
}

export async function disableScreenshotPrevention(): Promise<void> {
  if (!screenshotPreventionActive) return;
  try {
    if (Platform.OS === 'android') {
      const { NativeModules } = require('react-native');
      NativeModules.RNPreventScreenshot?.disableSecureView?.();
    } else {
      const PreventScreenshot = require('react-native-prevent-screenshot').default;
      PreventScreenshot.enabled(false);
    }
    screenshotPreventionActive = false;
  } catch (err) {
    console.warn('[HIPAA] Screenshot prevention disable failed:', err);
  }
}

// ---------------------------------------------------------------------------
// Biometric authentication
// ---------------------------------------------------------------------------

const rnBiometrics = new ReactNativeBiometrics({ allowDeviceCredentials: true });

export async function isBiometricAvailable(): Promise<boolean> {
  const { available } = await rnBiometrics.isSensorAvailable();
  return available;
}

export async function getBiometricType(): Promise<string> {
  const { biometryType } = await rnBiometrics.isSensorAvailable();
  if (!biometryType) return 'PIN';
  if (biometryType === BiometryTypes.FaceID) return 'Face ID';
  if (biometryType === BiometryTypes.TouchID) return 'Touch ID';
  return 'Biometric';
}

/**
 * Prompt biometric or device credential authentication.
 * Returns true if authenticated, false if cancelled or failed.
 */
export async function authenticateUser(prompt?: string): Promise<boolean> {
  try {
    const { success } = await rnBiometrics.simplePrompt({
      promptMessage: prompt ?? 'Authenticate to continue',
      cancelButtonText: 'Cancel',
      fallbackPromptMessage: 'Use passcode',
    });
    return success;
  } catch (err) {
    console.error('[HIPAA] Biometric auth error:', err);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Auto-lock manager
// ---------------------------------------------------------------------------

type LockCallback = () => void;

class AutoLockManager {
  private timer: ReturnType<typeof setTimeout> | null = null;
  private lockCallback: LockCallback | null = null;
  private appStateSubscription: ReturnType<typeof AppState.addEventListener> | null = null;
  private timeoutMs: number = AUTO_LOCK_TIMEOUT_MS;

  init(lockCallback: LockCallback, timeoutMs?: number): void {
    this.lockCallback = lockCallback;
    if (timeoutMs !== undefined) this.timeoutMs = timeoutMs;

    this.resetTimer();

    this.appStateSubscription = AppState.addEventListener(
      'change',
      this.handleAppStateChange
    );
  }

  resetTimer = (): void => {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.lockCallback?.();
    }, this.timeoutMs);
  };

  private handleAppStateChange = (nextState: AppStateStatus): void => {
    if (nextState === 'active') {
      // App came to foreground — check if enough time has passed
      // Timer was not cleared while in background, so it fires naturally
      this.resetTimer();
    } else if (nextState === 'background') {
      // Lock immediately on background (HIPAA — no data visible after switch)
      if (this.timer) clearTimeout(this.timer);
      this.lockCallback?.();
    }
  };

  updateTimeout(newTimeoutMs: number): void {
    this.timeoutMs = newTimeoutMs;
    this.resetTimer();
  }

  destroy(): void {
    if (this.timer) clearTimeout(this.timer);
    this.appStateSubscription?.remove();
    this.lockCallback = null;
  }
}

export const autoLock = new AutoLockManager();
