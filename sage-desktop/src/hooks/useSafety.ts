import { useMutation } from "@tanstack/react-query";

import {
  classifyAsil,
  classifyIec62304,
  classifySil,
  runFmea,
  runFta,
} from "@/api/client";
import type {
  DesktopError,
  SafetyAsilResult,
  SafetyFmeaEntryInput,
  SafetyFmeaResult,
  SafetyFtaNode,
  SafetyFtaResult,
  SafetyIec62304Result,
  SafetySilResult,
} from "@/api/types";

// All five are mutations rather than queries: the engine is a pure function of
// operator-entered input, so there is nothing to fetch on mount and nothing to
// poll. Each runs only when the operator presses the button.

export function useFmea() {
  return useMutation<SafetyFmeaResult, DesktopError, SafetyFmeaEntryInput[]>({
    mutationFn: (entries) => runFmea(entries),
  });
}

export function useFta() {
  return useMutation<SafetyFtaResult, DesktopError, SafetyFtaNode>({
    mutationFn: (tree) => runFta(tree),
  });
}

interface AsilVars {
  severity: string;
  exposure: string;
  controllability: string;
}

export function useAsil() {
  return useMutation<SafetyAsilResult, DesktopError, AsilVars>({
    mutationFn: (v) => classifyAsil(v.severity, v.exposure, v.controllability),
  });
}

export function useSil() {
  return useMutation<SafetySilResult, DesktopError, number>({
    mutationFn: (pfh) => classifySil(pfh),
  });
}

export function useIec62304() {
  return useMutation<SafetyIec62304Result, DesktopError, string>({
    mutationFn: (riskLevel) => classifyIec62304(riskLevel),
  });
}
