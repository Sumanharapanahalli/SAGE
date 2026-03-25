import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { API_BASE_URL } from '../constants';
import type {
  FallAlert,
  DeviceStatus,
  EmergencyContact,
  AlertHistoryEntry,
  Patient,
  AppSettings,
} from '../types';
import { getStoredTokens, storeTokens, clearTokens } from './authStorage';

// ---------------------------------------------------------------------------
// Axios instance with auth interceptor + token refresh
// ---------------------------------------------------------------------------

let apiInstance: AxiosInstance | null = null;

function getApiInstance(): AxiosInstance {
  if (apiInstance) return apiInstance;

  apiInstance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 15_000,
    headers: { 'Content-Type': 'application/json' },
  });

  // Attach access token to every request
  apiInstance.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
    const { accessToken } = await getStoredTokens();
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  });

  // Handle 401 — attempt token refresh once
  apiInstance.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;
        try {
          const { refreshToken } = await getStoredTokens();
          if (!refreshToken) throw new Error('No refresh token');
          const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, { refreshToken });
          await storeTokens(data.accessToken, data.refreshToken);
          originalRequest.headers.Authorization = `Bearer ${data.accessToken}`;
          return apiInstance!(originalRequest);
        } catch {
          await clearTokens();
          throw error;
        }
      }
      return Promise.reject(error);
    }
  );

  return apiInstance;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function loginWithOAuth(
  authCode: string,
  redirectUri: string
): Promise<{ accessToken: string; refreshToken: string; userId: string }> {
  const { data } = await getApiInstance().post('/auth/token', {
    grant_type: 'authorization_code',
    code: authCode,
    redirect_uri: redirectUri,
  });
  await storeTokens(data.access_token, data.refresh_token);
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    userId: data.user_id,
  };
}

export async function logout(): Promise<void> {
  const { refreshToken } = await getStoredTokens();
  try {
    await getApiInstance().post('/auth/revoke', { token: refreshToken });
  } finally {
    await clearTokens();
  }
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export async function getActiveAlerts(): Promise<FallAlert[]> {
  const { data } = await getApiInstance().get<FallAlert[]>('/alerts/active');
  return data;
}

export async function acknowledgeAlert(alertId: string): Promise<void> {
  await getApiInstance().patch(`/alerts/${alertId}/acknowledge`);
}

export async function resolveAlert(alertId: string, resolution: string): Promise<void> {
  await getApiInstance().patch(`/alerts/${alertId}/resolve`, { resolution });
}

export async function markFalseAlarm(alertId: string): Promise<void> {
  await getApiInstance().patch(`/alerts/${alertId}/false-alarm`);
}

export async function getAlertHistory(params: {
  page?: number;
  limit?: number;
  from?: string;
  to?: string;
  severity?: string;
}): Promise<{ items: AlertHistoryEntry[]; total: number; page: number }> {
  const { data } = await getApiInstance().get('/alerts/history', { params });
  return data;
}

export async function getAlertById(alertId: string): Promise<AlertHistoryEntry> {
  const { data } = await getApiInstance().get<AlertHistoryEntry>(`/alerts/${alertId}`);
  return data;
}

// ---------------------------------------------------------------------------
// Device
// ---------------------------------------------------------------------------

export async function getDeviceStatus(deviceId: string): Promise<DeviceStatus> {
  const { data } = await getApiInstance().get<DeviceStatus>(`/devices/${deviceId}/status`);
  return data;
}

export async function getAllDevices(): Promise<DeviceStatus[]> {
  const { data } = await getApiInstance().get<DeviceStatus[]>('/devices');
  return data;
}

export async function getDeviceLocation(deviceId: string): Promise<{
  latitude: number;
  longitude: number;
  accuracy: number;
  timestamp: number;
}> {
  const { data } = await getApiInstance().get(`/devices/${deviceId}/location`);
  return data;
}

export async function registerDevice(bleId: string, deviceName: string): Promise<DeviceStatus> {
  const { data } = await getApiInstance().post<DeviceStatus>('/devices/register', {
    ble_id: bleId,
    name: deviceName,
  });
  return data;
}

// ---------------------------------------------------------------------------
// Patients & Emergency Contacts
// ---------------------------------------------------------------------------

export async function getMyPatients(): Promise<Patient[]> {
  const { data } = await getApiInstance().get<Patient[]>('/patients');
  return data;
}

export async function getEmergencyContacts(patientId: string): Promise<EmergencyContact[]> {
  const { data } = await getApiInstance().get<EmergencyContact[]>(
    `/patients/${patientId}/emergency-contacts`
  );
  return data;
}

export async function createEmergencyContact(
  patientId: string,
  contact: Omit<EmergencyContact, 'id'>
): Promise<EmergencyContact> {
  const { data } = await getApiInstance().post<EmergencyContact>(
    `/patients/${patientId}/emergency-contacts`,
    contact
  );
  return data;
}

export async function updateEmergencyContact(
  patientId: string,
  contactId: string,
  updates: Partial<EmergencyContact>
): Promise<EmergencyContact> {
  const { data } = await getApiInstance().patch<EmergencyContact>(
    `/patients/${patientId}/emergency-contacts/${contactId}`,
    updates
  );
  return data;
}

export async function deleteEmergencyContact(patientId: string, contactId: string): Promise<void> {
  await getApiInstance().delete(`/patients/${patientId}/emergency-contacts/${contactId}`);
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export async function getUserSettings(): Promise<AppSettings> {
  const { data } = await getApiInstance().get<AppSettings>('/users/me/settings');
  return data;
}

export async function updateUserSettings(settings: Partial<AppSettings>): Promise<AppSettings> {
  const { data } = await getApiInstance().patch<AppSettings>('/users/me/settings', settings);
  return data;
}

// ---------------------------------------------------------------------------
// FCM token registration
// ---------------------------------------------------------------------------

export async function registerFCMToken(fcmToken: string, platform: 'ios' | 'android'): Promise<void> {
  await getApiInstance().post('/notifications/register', {
    token: fcmToken,
    platform,
  });
}

export async function unregisterFCMToken(fcmToken: string): Promise<void> {
  await getApiInstance().delete('/notifications/register', { data: { token: fcmToken } });
}
