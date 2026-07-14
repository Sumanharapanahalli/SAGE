import { useMutation, useQuery } from "@tanstack/react-query";

import {
  regulatoryAssess,
  regulatoryChecklist,
  regulatoryGapAnalysis,
  regulatoryRoadmap,
  regulatoryStandards,
} from "@/api/client";
import type {
  DesktopError,
  ProductProfile,
  RegulatoryAssessResult,
  RegulatoryChecklist,
  RegulatoryGapAnalysis,
  RegulatoryRoadmap,
  RegulatoryStandardsResult,
} from "@/api/types";

export function useRegulatoryStandards() {
  return useQuery<RegulatoryStandardsResult, DesktopError>({
    queryKey: ["regulatoryStandards"],
    queryFn: () => regulatoryStandards(),
  });
}

export function useRegulatoryChecklist(standardId: string) {
  return useQuery<RegulatoryChecklist, DesktopError>({
    queryKey: ["regulatoryChecklist", standardId],
    queryFn: () => regulatoryChecklist(standardId),
    enabled: standardId.length > 0,
  });
}

interface AssessVars {
  product: ProductProfile;
  standard_ids?: string[];
}

/** Assessment is an explicit operator action (it scores a product profile the
 * operator just typed) — a mutation, not an auto-firing query. Same shape as
 * useAssessComplianceGap. */
export function useRegulatoryAssess() {
  return useMutation<RegulatoryAssessResult, DesktopError, AssessVars>({
    mutationFn: (v) => regulatoryAssess(v.product, v.standard_ids),
  });
}

interface GapVars {
  product: ProductProfile;
  standard_id: string;
}

export function useRegulatoryGapAnalysis() {
  return useMutation<RegulatoryGapAnalysis, DesktopError, GapVars>({
    mutationFn: (v) => regulatoryGapAnalysis(v.product, v.standard_id),
  });
}

export function useRegulatoryRoadmap() {
  return useMutation<RegulatoryRoadmap, DesktopError, ProductProfile>({
    mutationFn: (product) => regulatoryRoadmap(product),
  });
}
