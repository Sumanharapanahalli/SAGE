export const API_BASE_URL = process.env.REACT_APP_API_URL ?? 'https://api.sage-elder-care.com/v1';
export const FCM_SENDER_ID = process.env.FCM_SENDER_ID ?? '';

// HIPAA compliance
export const AUTO_LOCK_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes
export const GPS_REFRESH_INTERVAL_MS = 4000; // 4s — safely under 5s SLA
export const ALERT_POLL_INTERVAL_MS = 10_000;

// BLE
export const SAGE_DEVICE_SERVICE_UUID = '6E400001-B5A3-F393-E0A9-E50E24DCCA9E';
export const SAGE_DEVICE_TX_CHAR_UUID = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E';
export const SAGE_DEVICE_RX_CHAR_UUID = '6E400002-B5A3-F393-E0A9-E50E24DCCA9E';
export const BLE_SCAN_TIMEOUT_MS = 10_000;

// Severity colors
export const SEVERITY_COLORS: Record<string, string> = {
  low: '#22c55e',
  moderate: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
};

export const SEVERITY_LABELS: Record<string, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  critical: 'Critical',
};

// MIME type for push notification channel (Android)
export const ALERT_CHANNEL_ID = 'sage_fall_alerts';
export const ALERT_CHANNEL_NAME = 'Fall Alerts';
