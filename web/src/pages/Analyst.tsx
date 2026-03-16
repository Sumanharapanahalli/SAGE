import { useState } from 'react'
import LogAnalysisForm from '../components/analyst/LogAnalysisForm'
import ProposalCard from '../components/analyst/ProposalCard'
import ApprovalButtons from '../components/analyst/ApprovalButtons'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import { useProjectConfig } from '../hooks/useProjectConfig'
import type { AnalysisResponse } from '../api/client'

export default function Analyst() {
  const [proposal, setProposal] = useState<AnalysisResponse | null>(null)
  const { data: projectData } = useProjectConfig()

  const labels = (projectData?.ui_labels ?? {}) as Record<string, string>
  const inputLabel = labels.analyst_input_label ?? 'Paste error log or metric report here...'

  return (
    <ModuleWrapper moduleId="analyst">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <LogAnalysisForm onResult={setProposal} placeholder={inputLabel} />
        </div>
        <div className="space-y-4">
          {proposal ? (
            <>
              <ProposalCard proposal={proposal} />
              <ApprovalButtons
                traceId={proposal.trace_id}
                onDone={() => setProposal(null)}
              />
            </>
          ) : (
            <div className="bg-white rounded-xl border border-dashed border-gray-300 p-8 flex items-center justify-center text-gray-400 text-sm">
              Analysis results will appear here
            </div>
          )}
        </div>
      </div>
    </ModuleWrapper>
  )
}
