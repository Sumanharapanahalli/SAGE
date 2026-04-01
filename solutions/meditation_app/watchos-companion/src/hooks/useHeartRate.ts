import { useState, useEffect, useRef } from 'react';

/** Simulates HKWorkoutSession heart rate samples (HealthKit).
 *  Update cadence: every 2 s (matches watchOS workout HR update frequency).
 *  Model: resting HR 68 bpm, trends down ≤8 bpm over 3 min of deep breathing,
 *         ±3 bpm Gaussian noise per sample — realistic for parasympathetic activation. */

const BASE_HR = 68;       // resting bpm
const MAX_REDUCTION = 8;  // max HR drop from deep breathing
const FULL_EFFECT_S = 180; // seconds to reach full HR reduction
const UPDATE_MS = 2000;   // HealthKit workout HR sample interval

export function useHeartRate(elapsedSeconds: number): { heartRate: number } {
  const [heartRate, setHeartRate] = useState<number>(BASE_HR);
  const elapsedRef = useRef(elapsedSeconds);

  useEffect(() => {
    elapsedRef.current = elapsedSeconds;
  }, [elapsedSeconds]);

  useEffect(() => {
    // First reading immediately on session start
    setHeartRate(BASE_HR + Math.round((Math.random() - 0.5) * 4));

    const interval = setInterval(() => {
      const elapsed = elapsedRef.current;
      // Parasympathetic reduction trend (linear → plateau)
      const reductionFactor = Math.min(elapsed / FULL_EFFECT_S, 1);
      const reduction = MAX_REDUCTION * reductionFactor;
      // Gaussian noise via Box–Muller (simplified single-sample)
      const u = Math.random();
      const noise = (u + Math.random() + Math.random() + Math.random() - 2) * 3;
      const newHR = Math.round(BASE_HR - reduction + noise);
      setHeartRate(Math.max(42, Math.min(105, newHR)));
    }, UPDATE_MS);

    return () => clearInterval(interval);
  }, []); // intentional: start once, read elapsed via ref

  return { heartRate };
}
