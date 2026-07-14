import { useQuery } from "@tanstack/react-query";

import { listActivity, type ListActivityParams } from "@/api/client";
import type { ActivityListResponse, DesktopError } from "@/api/types";

export const activityListKey = (params: ListActivityParams) =>
  ["activity", "list", params] as const;

export function useActivity(params: ListActivityParams = {}) {
  return useQuery<ActivityListResponse, DesktopError>({
    queryKey: activityListKey(params),
    queryFn: () => listActivity(params),
  });
}
