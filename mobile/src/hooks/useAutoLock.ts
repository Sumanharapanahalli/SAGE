/**
 * Hook that resets the auto-lock timer on any user touch/interaction.
 * Attach onTouchStart to the root PanResponder in AppContainer.
 */
import { useEffect, useRef, useCallback } from 'react';
import { PanResponder } from 'react-native';
import { autoLock } from '../services/hipaaService';

interface UseAutoLockOptions {
  onLock: () => void;
  timeoutMs?: number;
  enabled?: boolean;
}

export function useAutoLock({ onLock, timeoutMs, enabled = true }: UseAutoLockOptions) {
  const onLockRef = useRef(onLock);
  onLockRef.current = onLock;

  useEffect(() => {
    if (!enabled) return;
    autoLock.init(() => onLockRef.current(), timeoutMs);
    return () => autoLock.destroy();
  }, [enabled, timeoutMs]);

  const handleUserActivity = useCallback(() => {
    if (enabled) autoLock.resetTimer();
  }, [enabled]);

  // PanResponder that captures touches without blocking the responder chain
  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponderCapture: () => {
        handleUserActivity();
        return false; // don't consume the touch
      },
    })
  ).current;

  return { panHandlers: panResponder.panHandlers, handleUserActivity };
}
