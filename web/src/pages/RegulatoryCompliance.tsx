import { useState, useEffect } from 'react'
import { Shield, CheckCircle, XCircle, AlertTriangle, Globe, FileCheck, Map, ChevronDown } from 'lucide-react'
import { toast } from 'sonner'
import { fetchRegulatoryStandards, assessRegulatoryCompliance, generateRegulatoryRoadmap, generateFullRegulatoryReport } from '../api/client'

type Tab = 'dashboard' | 'assess' | 'roadmap'

const REGIONS = ['us', 'eu', 'uk', 'canada', 'japan', 'australia']
const RISK_CLASSES = ['I', 'II', 'IIa', 'IIb', 'III', 'IV']

const ARTIFACT_OPTIONS = [
  'software_development_plan', 'software_requirements_spec', 'software_architecture_doc',
  'software_detailed_design', 'risk_management_plan', 'risk_management_file',
  'validation_plan', 'validation_report', 'verification_plan', 'traceability_matrix',
  'test_protocols', 'test_reports', 'unit_test_reports', 'integration_test_reports',
  'system_test_reports', 'defect_log', 'configuration_management_plan', 'audit_trail',
  'soup_inventory', 'safety_classification', 'maintenance_plan', 'threat_model', 'sbom',
  'clinical_evaluation_report', 'technical_documentation', 'post_market_surveillance_plan',
  'electronic_signature_system', 'cds_classification_report', 'transparency_report',
]

export default function RegulatoryCompliance() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard')
  const [isLoading, setIsLoading] = useState(false)
  const [standards, setStandards] = useState<Array<Record<string, unknown>>>([])

  // Product profile form
  const [productName, setProductName] = useState('')
  const [riskClass, setRiskClass] = useState('II')
  const [regions, setRegions] = useState<string[]>(['us'])
  const [usesAiMl, setUsesAiMl] = useState(false)
  const [processesImages, setProcessesImages] = useState(false)
  const [artifacts, setArtifacts] = useState<string[]>([])

  // Results
  const [assessResult, setAssessResult] = useState<Record<string, unknown> | null>(null)
  const [roadmapResult, setRoadmapResult] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    fetchRegulatoryStandards()
      .then(setStandards)
      .catch(() => toast.error('Failed to load standards'))
  }, [])

  const buildProduct = () => ({
    product_name: productName || 'My Product',
    product_type: 'samd',
    risk_class: riskClass,
    target_regions: regions,
    uses_ai_ml: usesAiMl,
    processes_images: processesImages,
    processes_signals: false,
    existing_artifacts: artifacts,
  })

  const handleAssess = async () => {
    setIsLoading(true)
    try {
      const result = await assessRegulatoryCompliance({ product: buildProduct() })
      setAssessResult(result)
      toast.success('Assessment complete')
    } catch (e) { toast.error('Assessment failed: ' + (e as Error).message) }
    finally { setIsLoading(false) }
  }

  const handleRoadmap = async () => {
    setIsLoading(true)
    try {
      const result = await generateRegulatoryRoadmap(buildProduct())
      setRoadmapResult(result)
      toast.success('Roadmap generated')
    } catch (e) { toast.error('Roadmap failed: ' + (e as Error).message) }
    finally { setIsLoading(false) }
  }

  const toggleRegion = (r: string) => {
    setRegions(prev => prev.includes(r) ? prev.filter(x => x !== r) : [...prev, r])
  }

  const toggleArtifact = (a: string) => {
    setArtifacts(prev => prev.includes(a) ? prev.filter(x => x !== a) : [...prev, a])
  }

  const scoreColor = (score: number) =>
    score >= 80 ? 'text-orange-600 bg-orange-50' : score >= 50 ? 'text-yellow-600 bg-yellow-50' : 'text-red-600 bg-red-50'

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: 'dashboard', label: 'Standards', icon: Globe },
    { id: 'assess', label: 'Assess', icon: FileCheck },
    { id: 'roadmap', label: 'Roadmap', icon: Map },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Regulatory Compliance</h1>
          <p className="text-sm text-gray-600 mt-1">Multi-standard compliance assessment across FDA, EU, and international regulations</p>
        </div>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
          <Globe className="w-3.5 h-3.5" /> {standards.length} Standards
        </span>
      </div>

      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-1.5 ${
                activeTab === tab.id ? 'border-purple-500 text-purple-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              <tab.icon className="w-4 h-4" /> {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ========== STANDARDS DASHBOARD ========== */}
      {activeTab === 'dashboard' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {standards.map((std) => {
            const regionColors: Record<string, string> = {
              us: 'bg-blue-100 text-blue-800',
              eu: 'bg-indigo-100 text-indigo-800',
              uk: 'bg-red-100 text-red-800',
              international: 'bg-orange-100 text-orange-800',
              canada: 'bg-red-100 text-red-700',
              japan: 'bg-pink-100 text-pink-800',
              australia: 'bg-yellow-100 text-yellow-800',
            }
            return (
              <div key={std.id as string} className="bg-white shadow rounded-lg p-4 border border-gray-100">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-sm text-gray-900 leading-tight">{std.name as string}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${regionColors[(std.region as string)] || 'bg-gray-100 text-gray-700'}`}>
                    {(std.region as string).toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mb-3">{std.reference as string}</p>
                <div className="flex items-center gap-2 text-xs text-gray-600">
                  <span>{(std.requirements as string[]).length} requirements</span>
                  <span>|</span>
                  <span>{(std.required_artifacts as string[]).length} artifacts</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ========== ASSESS TAB ========== */}
      {activeTab === 'assess' && (
        <div className="space-y-6">
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">Product Profile</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Product Name</label>
                <input data-testid="reg-product-name" value={productName} onChange={e => setProductName(e.target.value)}
                  className="w-full border rounded-md p-2 text-sm" placeholder="e.g., CardioRisk CDS" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Risk Class</label>
                <select value={riskClass} onChange={e => setRiskClass(e.target.value)} className="w-full border rounded-md p-2 text-sm">
                  {RISK_CLASSES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Target Regions</label>
                <div className="flex flex-wrap gap-2">
                  {REGIONS.map(r => (
                    <button key={r} onClick={() => toggleRegion(r)}
                      className={`px-3 py-1 rounded-full text-xs font-medium border ${
                        regions.includes(r) ? 'bg-purple-100 text-purple-800 border-purple-300' : 'bg-gray-50 text-gray-600 border-gray-200'
                      }`}>
                      {r.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={usesAiMl} onChange={e => setUsesAiMl(e.target.checked)} className="rounded" />
                  Uses AI/ML
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={processesImages} onChange={e => setProcessesImages(e.target.checked)} className="rounded" />
                  Processes Images
                </label>
              </div>
            </div>

            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">Existing Artifacts (select all that apply)</label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-1 max-h-48 overflow-y-auto border rounded-md p-2">
                {ARTIFACT_OPTIONS.map(a => (
                  <label key={a} className="flex items-center gap-1.5 text-xs p-1 hover:bg-gray-50 rounded cursor-pointer">
                    <input type="checkbox" checked={artifacts.includes(a)} onChange={() => toggleArtifact(a)} className="rounded" />
                    {a.replace(/_/g, ' ')}
                  </label>
                ))}
              </div>
            </div>

            <button data-testid="assess-btn" onClick={handleAssess} disabled={isLoading}
              className="mt-4 px-4 py-2 bg-purple-600 text-white rounded-md text-sm font-medium hover:bg-purple-700 disabled:opacity-50">
              {isLoading ? 'Assessing...' : 'Assess Compliance'}
            </button>
          </div>

          {assessResult && (
            <div className="space-y-4">
              <div className={`p-4 rounded-lg text-center ${scoreColor((assessResult as { overall_score: number }).overall_score)}`}>
                <span className="text-3xl font-bold">{(assessResult as { overall_score: number }).overall_score}%</span>
                <p className="text-sm mt-1">Overall Compliance Score ({(assessResult as { standards_assessed: number }).standards_assessed} standards)</p>
              </div>

              <div className="space-y-2">
                {Object.entries((assessResult as { assessments: Record<string, Record<string, unknown>> }).assessments).map(([stdId, assessment]) => (
                  <details key={stdId} className="bg-white shadow rounded-lg border">
                    <summary className="p-4 cursor-pointer flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {(assessment.compliance_score as number) >= 80
                          ? <CheckCircle className="w-5 h-5 text-orange-500" />
                          : (assessment.compliance_score as number) >= 50
                          ? <AlertTriangle className="w-5 h-5 text-yellow-500" />
                          : <XCircle className="w-5 h-5 text-red-500" />}
                        <div>
                          <span className="font-medium text-sm">{assessment.standard_name as string}</span>
                          <span className="text-xs text-gray-500 ml-2">({(assessment.region as string).toUpperCase()})</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-bold px-2 py-0.5 rounded ${scoreColor(assessment.compliance_score as number)}`}>
                          {assessment.compliance_score as number}%
                        </span>
                        <ChevronDown className="w-4 h-4 text-gray-400" />
                      </div>
                    </summary>
                    <div className="px-4 pb-4 border-t pt-3">
                      {(assessment.gaps as string[]).length > 0 && (
                        <div className="mb-3">
                          <h4 className="text-xs font-semibold text-red-700 mb-1">Gaps ({(assessment.gaps as string[]).length})</h4>
                          <ul className="text-xs text-gray-700 space-y-1">
                            {(assessment.gaps as string[]).slice(0, 5).map((gap, i) => (
                              <li key={i} className="flex items-start gap-1"><XCircle className="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" /> {gap}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {(assessment.missing_artifacts as string[]).length > 0 && (
                        <div>
                          <h4 className="text-xs font-semibold text-yellow-700 mb-1">Missing Artifacts</h4>
                          <div className="flex flex-wrap gap-1">
                            {(assessment.missing_artifacts as string[]).map((a, i) => (
                              <span key={i} className="text-xs px-2 py-0.5 bg-yellow-50 text-yellow-700 rounded">{a.replace(/_/g, ' ')}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </details>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========== ROADMAP TAB ========== */}
      {activeTab === 'roadmap' && (
        <div className="space-y-6">
          <div className="bg-white shadow rounded-lg p-6">
            <p className="text-sm text-gray-600 mb-4">Generate a phased submission roadmap based on your product profile and target regions.</p>
            <button data-testid="roadmap-btn" onClick={handleRoadmap} disabled={isLoading}
              className="px-4 py-2 bg-purple-600 text-white rounded-md text-sm font-medium hover:bg-purple-700 disabled:opacity-50">
              {isLoading ? 'Generating...' : 'Generate Roadmap'}
            </button>
          </div>

          {roadmapResult && (
            <div className="space-y-4">
              <div className="bg-purple-50 rounded-lg p-4 text-center">
                <span className="text-lg font-bold text-purple-800">
                  {(roadmapResult as { total_estimated_weeks: number }).total_estimated_weeks} weeks estimated
                </span>
                <p className="text-xs text-purple-600 mt-1">
                  Regions: {((roadmapResult as { target_regions: string[] }).target_regions || []).map(r => r.toUpperCase()).join(', ')}
                </p>
              </div>
              {((roadmapResult as { phases: Array<Record<string, unknown>> }).phases || []).map((phase, i) => (
                <div key={i} className="bg-white shadow rounded-lg p-4 border-l-4 border-purple-400">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-sm">{phase.phase_name as string}</h3>
                    <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">{phase.estimated_weeks as number} weeks</span>
                  </div>
                  <p className="text-xs text-gray-600 mb-2">{phase.description as string}</p>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {(phase.standards as string[]).map(s => (
                      <span key={s} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-700 rounded font-mono">{s}</span>
                    ))}
                  </div>
                  <ul className="text-xs text-gray-700 space-y-0.5">
                    {(phase.deliverables as string[]).map((d, j) => (
                      <li key={j} className="flex items-center gap-1"><FileCheck className="w-3 h-3 text-gray-400" /> {d}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
