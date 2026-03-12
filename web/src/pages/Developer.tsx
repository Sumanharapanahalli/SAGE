import MRCreateForm from '../components/developer/MRCreateForm'
import MRReviewPanel from '../components/developer/MRReviewPanel'
import OpenMRsList from '../components/developer/OpenMRsList'
import ModuleWrapper from '../components/shared/ModuleWrapper'

export default function Developer() {
  return (
    <ModuleWrapper moduleId="developer">
      <div className="space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MRCreateForm />
          <MRReviewPanel />
        </div>
        <OpenMRsList />
      </div>
    </ModuleWrapper>
  )
}
