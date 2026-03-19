import OnboardingWizard from '../components/onboarding/OnboardingWizard'
import { useTourContext } from '../context/TourContext'
import { useNavigate } from 'react-router-dom'

export default function Onboarding() {
  const { startTour } = useTourContext()
  const navigate = useNavigate()
  return (
    <OnboardingWizard
      onClose={() => navigate('/')}
      onTourStart={(solutionId) => { startTour(solutionId); navigate('/') }}
    />
  )
}
