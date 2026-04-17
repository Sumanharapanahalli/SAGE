import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as client from "@/api/client";
import type {
  DesktopError,
  FeatureRequest,
  FeatureRequestScope,
  FeatureRequestStatus,
  FeatureRequestSubmit,
  FeatureRequestUpdate,
} from "@/api/types";

export const useFeatureRequests = (
  params: { status?: FeatureRequestStatus; scope?: FeatureRequestScope } = {},
) =>
  useQuery<FeatureRequest[], DesktopError>({
    queryKey: ["backlog", params.status ?? "all", params.scope ?? "all"],
    queryFn: () => client.listFeatureRequests(params),
  });

export const useSubmitFeatureRequest = () => {
  const qc = useQueryClient();
  return useMutation<FeatureRequest, DesktopError, FeatureRequestSubmit>({
    mutationFn: (req) => client.submitFeatureRequest(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backlog"] }),
  });
};

export const useUpdateFeatureRequest = () => {
  const qc = useQueryClient();
  return useMutation<FeatureRequest, DesktopError, FeatureRequestUpdate>({
    mutationFn: (req) => client.updateFeatureRequest(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backlog"] }),
  });
};
