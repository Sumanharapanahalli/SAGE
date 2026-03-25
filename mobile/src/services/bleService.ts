/**
 * BLE service using react-native-ble-plx.
 * Pairing flow: Scan → Select → Confirm (3 steps, as required).
 */
import { BleManager, Device, State, ScanCallbackType, ScanMode } from 'react-native-ble-plx';
import { Platform, PermissionsAndroid } from 'react-native';
import { Buffer } from 'buffer';
import {
  SAGE_DEVICE_SERVICE_UUID,
  SAGE_DEVICE_TX_CHAR_UUID,
  SAGE_DEVICE_RX_CHAR_UUID,
  BLE_SCAN_TIMEOUT_MS,
} from '../constants';
import type { BLEDevice } from '../types';

let bleManager: BleManager | null = null;

function getManager(): BleManager {
  if (!bleManager) bleManager = new BleManager();
  return bleManager;
}

// ---------------------------------------------------------------------------
// Permissions (Android 12+ requires BLUETOOTH_SCAN + BLUETOOTH_CONNECT)
// ---------------------------------------------------------------------------

export async function requestBLEPermissions(): Promise<boolean> {
  if (Platform.OS !== 'android') return true;
  if (Platform.Version < 31) {
    const granted = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION
    );
    return granted === PermissionsAndroid.RESULTS.GRANTED;
  }
  const results = await PermissionsAndroid.requestMultiple([
    PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
    PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
    PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
  ]);
  return Object.values(results).every((r) => r === PermissionsAndroid.RESULTS.GRANTED);
}

// ---------------------------------------------------------------------------
// Wait for BLE to be powered on
// ---------------------------------------------------------------------------

export async function waitForBLEReady(timeoutMs = 5000): Promise<boolean> {
  return new Promise((resolve) => {
    const mgr = getManager();
    const timer = setTimeout(() => resolve(false), timeoutMs);
    mgr.onStateChange((state) => {
      if (state === State.PoweredOn) {
        clearTimeout(timer);
        resolve(true);
      }
    }, true);
  });
}

// ---------------------------------------------------------------------------
// STEP 1: Scan for SAGE devices
// ---------------------------------------------------------------------------

export function scanForDevices(
  onDeviceFound: (device: BLEDevice) => void,
  onError: (error: Error) => void
): () => void {
  const mgr = getManager();
  const seen = new Set<string>();

  mgr.startDeviceScan(
    [SAGE_DEVICE_SERVICE_UUID],
    { scanMode: ScanMode.LowLatency, callbackType: ScanCallbackType.AllMatches },
    (error, device) => {
      if (error) {
        onError(error);
        return;
      }
      if (!device || seen.has(device.id)) return;
      seen.add(device.id);
      onDeviceFound({
        id: device.id,
        name: device.name ?? device.localName ?? null,
        rssi: device.rssi ?? -100,
        serviceUUIDs: device.serviceUUIDs ?? [],
        isConnectable: device.isConnectable ?? true,
      });
    }
  );

  const stopTimer = setTimeout(() => mgr.stopDeviceScan(), BLE_SCAN_TIMEOUT_MS);

  return () => {
    clearTimeout(stopTimer);
    mgr.stopDeviceScan();
  };
}

// ---------------------------------------------------------------------------
// STEP 2: Connect to selected device
// ---------------------------------------------------------------------------

export async function connectToDevice(deviceId: string): Promise<Device> {
  const mgr = getManager();
  mgr.stopDeviceScan();

  const device = await mgr.connectToDevice(deviceId, {
    autoConnect: false,
    timeout: 10_000,
  });
  await device.discoverAllServicesAndCharacteristics();
  return device;
}

// ---------------------------------------------------------------------------
// STEP 3: Confirm pairing — exchange credentials / device ID
// ---------------------------------------------------------------------------

export async function confirmPairing(
  device: Device,
  caregiverId: string
): Promise<{ deviceName: string; firmwareVersion: string }> {
  // Send pairing request
  const request = JSON.stringify({ type: 'PAIR', caregiver_id: caregiverId });
  const encoded = Buffer.from(request).toString('base64');
  await device.writeCharacteristicWithResponseForService(
    SAGE_DEVICE_SERVICE_UUID,
    SAGE_DEVICE_RX_CHAR_UUID,
    encoded
  );

  // Wait for acknowledgement
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Pairing timeout')), 10_000);

    device.monitorCharacteristicForService(
      SAGE_DEVICE_SERVICE_UUID,
      SAGE_DEVICE_TX_CHAR_UUID,
      (error, characteristic) => {
        if (error) {
          clearTimeout(timeout);
          reject(error);
          return;
        }
        if (!characteristic?.value) return;
        try {
          const decoded = Buffer.from(characteristic.value, 'base64').toString('utf8');
          const response = JSON.parse(decoded);
          if (response.type === 'PAIR_ACK') {
            clearTimeout(timeout);
            resolve({
              deviceName: response.device_name ?? 'SAGE Device',
              firmwareVersion: response.firmware_version ?? 'unknown',
            });
          } else if (response.type === 'PAIR_ERROR') {
            clearTimeout(timeout);
            reject(new Error(response.message ?? 'Pairing rejected by device'));
          }
        } catch (parseError) {
          clearTimeout(timeout);
          reject(parseError);
        }
      }
    );
  });
}

// ---------------------------------------------------------------------------
// Disconnect
// ---------------------------------------------------------------------------

export async function disconnectDevice(deviceId: string): Promise<void> {
  const mgr = getManager();
  const isConnected = await mgr.isDeviceConnected(deviceId);
  if (isConnected) {
    await mgr.cancelDeviceConnection(deviceId);
  }
}

// ---------------------------------------------------------------------------
// Cleanup
// ---------------------------------------------------------------------------

export function destroyBLEManager(): void {
  bleManager?.destroy();
  bleManager = null;
}
