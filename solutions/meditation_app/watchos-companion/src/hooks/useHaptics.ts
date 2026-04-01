/** Simulates WKHapticType via Web Vibration API.
 *  On devices without navigator.vibrate, falls back gracefully (visual-only).
 *  Pattern mapping mirrors Apple Watch haptic vocabulary:
 *    success  → WKHapticType.success  (double tap + long)
 *    tap      → WKHapticType.click    (single short)
 *    warning  → WKHapticType.failure  (double long)
 */

const HAPTIC_PATTERNS: Record<string, number[]> = {
  success: [80, 40, 80, 40, 200],
  tap:     [50],
  warning: [180, 80, 180],
};

export type HapticType = keyof typeof HAPTIC_PATTERNS;

export function useHaptics() {
  const isSupported =
    typeof navigator !== 'undefined' && 'vibrate' in navigator;

  const triggerHaptic = (type: HapticType = 'tap'): void => {
    if (isSupported) {
      navigator.vibrate(HAPTIC_PATTERNS[type]);
    }
    // Visual haptic is handled by .haptic-flash CSS animation in the view
  };

  return { triggerHaptic, isSupported };
}
