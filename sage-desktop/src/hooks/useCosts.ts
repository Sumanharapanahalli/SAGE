import { useMutation, useQuery } from "@tanstack/react-query";

import { getCostsDaily, getCostsSummary, setCostsBudget } from "@/api/client";
import type {
  CostBudgetResult,
  CostDailyResult,
  CostSummary,
  DesktopError,
} from "@/api/types";

export function useCostsSummary(
  tenant?: string,
  solution?: string,
  periodDays?: number,
) {
  return useQuery<CostSummary, DesktopError>({
    queryKey: ["costsSummary", tenant, solution, periodDays],
    queryFn: () => getCostsSummary(tenant, solution, periodDays),
  });
}

export function useCostsDaily(
  tenant?: string,
  solution?: string,
  periodDays?: number,
) {
  return useQuery<CostDailyResult, DesktopError>({
    queryKey: ["costsDaily", tenant, solution, periodDays],
    queryFn: () => getCostsDaily(tenant, solution, periodDays),
  });
}

interface SetBudgetVars {
  monthly_usd: number;
  tenant?: string;
  solution?: string;
}

export function useSetCostsBudget() {
  return useMutation<CostBudgetResult, DesktopError, SetBudgetVars>({
    mutationFn: (v) => setCostsBudget(v.monthly_usd, v.tenant, v.solution),
  });
}
