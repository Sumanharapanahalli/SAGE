import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as client from "@/api/client";
import type {
  DesktopError,
  Goal,
  GoalCreateParams,
  GoalDeleteResult,
  GoalListParams,
  GoalUpdateParams,
} from "@/api/types";

export const goalsKey = ["goals"];

export const useGoals = (params: GoalListParams = {}) =>
  useQuery<Goal[], DesktopError>({
    queryKey: [...goalsKey, params],
    queryFn: () => client.listGoals(params),
  });

export const useCreateGoal = () => {
  const qc = useQueryClient();
  return useMutation<Goal, DesktopError, GoalCreateParams>({
    mutationFn: (params) => client.createGoal(params),
    onSuccess: () => qc.invalidateQueries({ queryKey: goalsKey }),
  });
};

export const useUpdateGoal = () => {
  const qc = useQueryClient();
  return useMutation<Goal, DesktopError, GoalUpdateParams>({
    mutationFn: (params) => client.updateGoal(params),
    onSuccess: () => qc.invalidateQueries({ queryKey: goalsKey }),
  });
};

export const useDeleteGoal = () => {
  const qc = useQueryClient();
  return useMutation<GoalDeleteResult, DesktopError, string>({
    mutationFn: (goal_id) => client.deleteGoal(goal_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: goalsKey }),
  });
};
