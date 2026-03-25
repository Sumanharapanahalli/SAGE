import { useEffect } from 'react';
import { enableScreenshotPrevention, disableScreenshotPrevention } from '../services/hipaaService';

/**
 * Enables screenshot prevention when the screen mounts, disables on unmount.
 * Use on DeviceStatusScreen and LiveMapScreen (HIPAA requirement).
 */
export function useScreenshotPrevention(enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    enableScreenshotPrevention();
    return () => {
      disableScreenshotPrevention();
    };
  }, [enabled]);
}
