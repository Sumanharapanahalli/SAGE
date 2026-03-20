import MRCreateForm from '../components/developer/MRCreateForm'
import MRReviewPanel from '../components/developer/MRReviewPanel'
import OpenMRsList from '../components/developer/OpenMRsList'
import ModuleWrapper from '../components/shared/ModuleWrapper'
import ResizablePanels from '../components/ui/ResizablePanels'

export default function Developer() {
  return (
    <ModuleWrapper moduleId="developer">
      <div className="space-y-6">
        <div style={{ height: 420 }}>
          <ResizablePanels
            direction="horizontal"
            storageKey="developer"
            defaultSplit={50}
            minFirst={280}
            minSecond={280}
            first={
              <div className="pr-3 h-full">
                <MRCreateForm />
              </div>
            }
            second={
              <div className="pl-3 h-full">
                <MRReviewPanel />
              </div>
            }
          />
        </div>
        <OpenMRsList />
      </div>
    </ModuleWrapper>
  )
}
