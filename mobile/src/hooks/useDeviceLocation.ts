import { useState, useEffect, useRef, useCallback } from 'react';
import { getDeviceLocation } from '../services/api';
import { GPS_REFRESH_INTERVAL_MS } from '../constants';
import type { GeoCoordinate } from '../types';

interface UseDeviceLocationResult {
  location: GeoCoordinate | null;
  error: string | null;
  isLoading: boolean;
  refresh: () => void;
}

/**
 * Polls device GPS location every GPS_REFRESH_INTERVAL_MS (4s, under the 5s SLA).
 */
export function useDeviceLocation(deviceId: string | null): UseDeviceLocationResult {
  const [location, setLocation] = useState<GeoCoordinate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  const fetch = useCallback(async () => {
    if (!deviceId) return;
    try {
      const loc = await getDeviceLocation(deviceId);
      if (mountedRef.current) {
        setLocation(loc);
        setError(null);
      }
    } catch (err: any) {
      if (mountedRef.current) {
        setError(err?.message ?? 'Location unavailable');
      }
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [deviceId]);

  useEffect(() => {
    mountedRef.current = true;
    if (!deviceId) return;

    setIsLoading(true);
    fetch();

    intervalRef.current = setInterval(fetch, GPS_REFRESH_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [deviceId, fetch]);

  return { location, error, isLoading, refresh: fetch };
}
