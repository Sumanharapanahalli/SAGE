import { useMutation, useQuery } from "@tanstack/react-query";

import {
  assessComplianceGap,
  getComplianceChecklist,
  listComplianceDomains,
} from "@/api/client";
import type {
  ComplianceChecklist,
  ComplianceDomainsResult,
  ComplianceGapResult,
  DesktopError,
} from "@/api/types";

export function useComplianceDomains() {
  return useQuery<ComplianceDomainsResult, DesktopError>({
    queryKey: ["complianceDomains"],
    queryFn: () => listComplianceDomains(),
  });
}

export function useComplianceChecklist(domain: string, riskLevel: string) {
  return useQuery<ComplianceChecklist, DesktopError>({
    queryKey: ["complianceChecklist", domain, riskLevel],
    queryFn: () => getComplianceChecklist(domain, riskLevel),
    enabled: domain.length > 0,
  });
}

interface GapAssessmentVars {
  domain: string;
  risk_level: string;
  completed_tasks: string[];
}

export function useAssessComplianceGap() {
  return useMutation<ComplianceGapResult, DesktopError, GapAssessmentVars>({
    mutationFn: (v) =>
      assessComplianceGap(v.domain, v.risk_level, v.completed_tasks),
  });
}
