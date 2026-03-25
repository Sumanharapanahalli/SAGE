// Core domain types for the Caregiver App

export type FallSeverity = 'low' | 'moderate' | 'high' | 'critical';

export type AlertStatus = 'active' | 'acknowledged' | 'resolved' | 'false_alarm';

export type DeviceConnectivity = 'cellular' | 'wifi' | 'bluetooth' | 'offline';

export interface GeoCoordinate {
  latitude: number;
  longitude: number;
  accuracy?: number;
  timestamp: number;
}

export interface FallAlert {
  id: string;
  deviceId: string;
  patientId: string;
  patientName: string;
  severity: FallSeverity;
  status: AlertStatus;
  timestamp: string; // ISO-8601
  location: GeoCoordinate;
  accelerometerData?: {
    x: number;
    y: number;
    z: number;
    impactForce: number; // g-force
  };
  notes?: string;
}

export interface DeviceStatus {
  deviceId: string;
  deviceName: string;
  batteryLevel: number; // 0-100
  isCharging: boolean;
  connectivity: DeviceConnectivity;
  signalStrength?: number; // dBm
  firmwareVersion: string;
  lastSeen: string; // ISO-8601
  location?: GeoCoordinate;
  isActive: boolean;
}

export interface EmergencyContact {
  id: string;
  name: string;
  relationship: string;
  phone: string;
  email?: string;
  isPrimary: boolean;
  notifyOnAlert: boolean;
  notifyBySMS: boolean;
  notifyByCall: boolean;
}

export interface Patient {
  id: string;
  name: string;
  dateOfBirth: string;
  medicalId: string;
  deviceId?: string;
  emergencyContacts: EmergencyContact[];
  caregivers: string[];
}

export interface AlertHistoryEntry extends FallAlert {
  responseTime?: number; // seconds
  respondedBy?: string;
  resolution?: string;
}

export interface BLEDevice {
  id: string;
  name: string | null;
  rssi: number;
  serviceUUIDs?: string[];
  isConnectable: boolean;
}

export interface NotificationPreferences {
  fallAlerts: boolean;
  lowBattery: boolean;
  deviceOffline: boolean;
  vibrate: boolean;
  sound: boolean;
  criticalAlertsOverride: boolean; // iOS critical alerts
  quietHoursEnabled: boolean;
  quietHoursStart: string; // HH:mm
  quietHoursEnd: string;   // HH:mm
}

export interface AppSettings {
  autoLockTimeout: number; // seconds, default 300 (5 min)
  biometricEnabled: boolean;
  theme: 'light' | 'dark' | 'system';
  notifications: NotificationPreferences;
  mapType: 'standard' | 'satellite' | 'hybrid';
  gpsRefreshInterval: number; // seconds, max 5
}

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  userId: string | null;
  isAuthenticated: boolean;
  isLocked: boolean;
}

export type RootStackParamList = {
  Auth: undefined;
  LockScreen: undefined;
  MainTabs: undefined;
  AlertDetail: { alertId: string };
  DevicePairing: undefined;
  AddEmergencyContact: { patientId: string; contactId?: string };
};

export type MainTabParamList = {
  AlertDashboard: undefined;
  LiveMap: undefined;
  DeviceStatus: undefined;
  EmergencyContacts: undefined;
  AlertHistory: undefined;
  Settings: undefined;
};
