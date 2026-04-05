import { useState } from 'react'
import { Shield, CheckCircle, XCircle, AlertTriangle, FileText, Eye, Database, Tag, Package } from 'lucide-react'
import { toast } from 'sonner'
import { classifyCDSFunction, classifyCDSInputs, validateCDSSources, classifyCDSOutput, generateCDSTransparencyReport, generateCDSLabeling, generateCDSCompliancePackage } from '../api/client'

type Tab = 'overview' | 'inputs' | 'sources' | 'labeling' | 'package'

interface DataSource { name: string; type: string }
interface CriterionResult { passes: boolean; rationale: string }
interface ClassificationResult {
  criterion_1: CriterionResult; criterion_2: CriterionResult;
  criterion_3: CriterionResult; criterion_4: CriterionResult;
  overall_classification: string
}

const SOURCE_TYPES = [
  'clinical_guideline', 'peer_reviewed', 'fda_labeling',
  'government', 'textbook', 'proprietary', 'novel',
]

const OUTPUT_TYPES = [
  'recommendation', 'single_recommendation', 'definitive_diagnosis', 'immediate_directive',
]

const URGENCY_OPTIONS = ['non_urgent', 'urgent', 'time_critical']

export default function CDSCompliance() {
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [isLoading, setIsLoading] = useState(false)

  // Overview form
  const [funcDesc, setFuncDesc] = useState('')
  const [inputTypes, setInputTypes] = useState('')
  const [outputType, setOutputType] = useState('recommendation')
  const [intendedUser, setIntendedUser] = useState('')
  const [urgency, setUrgency] = useState('non_urgent')
  const [sources, setSources] = useState<DataSource[]>([{ name: '', type: 'clinical_guideline' }])
  const [classResult, setClassResult] = useState<ClassificationResult | null>(null)

  // Input taxonomy
  const [inputTaxonomy, setInputTaxonomy] = useState<string>('')
  const [inputResults, setInputResults] = useState<Array<{ input_type: string; data_category: string; criterion_1_impact: string }>>([])

  // Source validation
  const [srcValidation, setSrcValidation] = useState<Record<string, unknown> | null>(null)

  // Labeling
  const [productName, setProductName] = useState('')
  const [algoSummary, setAlgoSummary] = useState('')
  const [targetPop, setTargetPop] = useState('')
  const [valSummary, setValSummary] = useState('')
  const [limitations, setLimitations] = useState('')
  const [labelResult, setLabelResult] = useState<Record<string, unknown> | null>(null)

  // Full package
  const [packageResult, setPackageResult] = useState<Record<string, unknown> | null>(null)

  const addSource = () => setSources([...sources, { name: '', type: 'clinical_guideline' }])
  const removeSource = (i: number) => setSources(sources.filter((_, idx) => idx !== i))
  const updateSource = (i: number, field: 'name' | 'type', value: string) => {
    const updated = [...sources]; updated[i] = { ...updated[i], [field]: value }; setSources(updated)
  }

  // --- Handlers ---

  const handleClassify = async () => {
    if (!funcDesc || !intendedUser) { toast.error('Fill in function description and intended user'); return }
    setIsLoading(true)
    try {
      const result = await classifyCDSFunction({
        function_description: funcDesc,
        input_types: inputTypes.split(',').map(s => s.trim()).filter(Boolean),
        output_type: outputType,
        intended_user: intendedUser,
        urgency,
        data_sources: sources.filter(s => s.name),
      })
      setClassResult(result as unknown as ClassificationResult)
      toast.success('Classification complete')
    } catch (e) { toast.error('Classification failed: ' + (e as Error).message) }
    finally { setIsLoading(false) }
  }

  const handleClassifyInputs = async () => {
    if (!inputTaxonomy) { toast.error('Enter input types'); return }
    setIsLoading(true)
    try {
      const result = await classifyCDSInputs(inputTaxonomy.split(',').map(s => s.trim()).filter(Boolean))
      setInputResults(result)
      toast.success('Input classification complete')
    } catch (e) { toast.error('Failed: ' + (e as Error).message) }
    finally { setIsLoading(false) }
  }

  const handleValidateSources = async () => {
    setIsLoading(true)
    try {
      const result = await validateCDSSources(sources.filter(s => s.name))
      setSrcValidation(result)
      toast.success('Source validation complete')
    } catch (e) { toast.error('Failed: ' + (e as Error).message) }
    finally { setIsLoading(false) }
  }

  const handleGenerateLabeling = async () => {
    if (!productName || !funcDesc) { toast.error('Fill in product name and function description'); return }
    setIsLoading(true)
    try {
      const result = await generateCDSLabeling({
        product_name: productName,
        intended_use: funcDesc,
        intended_users: [intendedUser || 'physician'],
        target_population: targetPop,
        algorithm_summary: algoSummary,
        data_sources: sources.filter(s => s.name),
        validation_summary: valSummary,
        known_limitations: limitations.split('\n').filter(Boolean),
      })
      setLabelResult(result)
      toast.success('Labeling generated')
    } catch (e) { toast.error('Failed: ' + (e as Error).message) }
    finally { setIsLoading(false) }
  }

  const handleGeneratePackage = async () => {
    if (!productName || !funcDesc) { toast.error('Fill in product name and function description'); return }
    setIsLoading(true)
    try {
      const result = await generateCDSCompliancePackage({
        product_name: productName || 'CDS Product',
        function_description: funcDesc,
        input_types: inputTypes.split(',').map(s => s.trim()).filter(Boolean),
        output_type: outputType,
        intended_user: intendedUser || 'physician',
        urgency,
        data_sources: sources.filter(s => s.name),
        algorithm_description: algoSummary || funcDesc,
        known_limitations: limitations.split('\n').filter(Boolean),
        target_population: targetPop || 'General adult population',
        validation_summary: valSummary || 'Pending validation',
      })
      setPackageResult(result)
      toast.success('Compliance package generated')
    } catch (e) { toast.error('Failed: ' + (e as Error).message) }
    finally { setIsLoading(false) }
  }

  // --- Criterion badge ---
  const CriterionBadge = ({ label, result }: { label: string; result?: CriterionResult }) => {
    if (!result) return null
    return (
      <div className={`p-4 rounded-lg border-2 ${result.passes ? 'border-green-300 bg-orange-50' : 'border-red-300 bg-red-50'}`}>
        <div className="flex items-center gap-2 mb-2">
          {result.passes ? <CheckCircle className="w-5 h-5 text-orange-600" /> : <XCircle className="w-5 h-5 text-red-600" />}
          <span className="font-semibold text-sm">{label}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${result.passes ? 'bg-orange-200 text-orange-800' : 'bg-red-200 text-red-800'}`}>
            {result.passes ? 'PASS' : 'FAIL'}
          </span>
        </div>
        <p className="text-xs text-gray-700">{result.rationale}</p>
      </div>
    )
  }

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: 'overview', label: 'Classification', icon: Shield },
    { id: 'inputs', label: 'Input Taxonomy', icon: Database },
    { id: 'sources', label: 'Data Sources', icon: Eye },
    { id: 'labeling', label: 'Labeling', icon: Tag },
    { id: 'package', label: 'Full Package', icon: Package },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">FDA CDS Compliance</h1>
          <p className="text-sm text-gray-600 mt-1">Clinical Decision Support Software Guidance (January 2026) - 4-Criterion Assessment</p>
        </div>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
          <Shield className="w-3.5 h-3.5" /> FDA media/109618
        </span>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-1.5 ${
                activeTab === tab.id ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              <tab.icon className="w-4 h-4" /> {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ============ OVERVIEW TAB ============ */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">CDS Function Classification</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Function Description</label>
                <textarea data-testid="func-desc" value={funcDesc} onChange={e => setFuncDesc(e.target.value)}
                  className="w-full border rounded-md p-2 text-sm" rows={3}
                  placeholder="e.g., Checks patient medication list against drug-drug interaction database" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Input Types (comma-separated)</label>
                <input data-testid="input-types" value={inputTypes} onChange={e => setInputTypes(e.target.value)}
                  className="w-full border rounded-md p-2 text-sm" placeholder="medication_list, allergy_list" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Output Type</label>
                <select data-testid="output-type" value={outputType} onChange={e => setOutputType(e.target.value)}
                  className="w-full border rounded-md p-2 text-sm">
                  {OUTPUT_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Intended User</label>
                <input data-testid="intended-user" value={intendedUser} onChange={e => setIntendedUser(e.target.value)}
                  className="w-full border rounded-md p-2 text-sm" placeholder="physician" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Urgency</label>
                <select data-testid="urgency" value={urgency} onChange={e => setUrgency(e.target.value)}
                  className="w-full border rounded-md p-2 text-sm">
                  {URGENCY_OPTIONS.map(u => <option key={u} value={u}>{u.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
            </div>

            {/* Data Sources */}
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">Data Sources</label>
              {sources.map((src, i) => (
                <div key={i} className="flex gap-2 mb-2">
                  <input value={src.name} onChange={e => updateSource(i, 'name', e.target.value)}
                    className="flex-1 border rounded-md p-2 text-sm" placeholder="Source name" />
                  <select value={src.type} onChange={e => updateSource(i, 'type', e.target.value)}
                    className="border rounded-md p-2 text-sm">
                    {SOURCE_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                  </select>
                  {sources.length > 1 && (
                    <button onClick={() => removeSource(i)} className="text-red-500 text-sm px-2">Remove</button>
                  )}
                </div>
              ))}
              <button onClick={addSource} className="text-blue-600 text-sm mt-1">+ Add Source</button>
            </div>

            <button data-testid="classify-btn" onClick={handleClassify} disabled={isLoading}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {isLoading ? 'Classifying...' : 'Classify Function'}
            </button>
          </div>

          {/* Results */}
          {classResult && (
            <div className="space-y-4">
              <div className={`p-4 rounded-lg text-center ${
                classResult.overall_classification === 'non_device_cds'
                  ? 'bg-orange-100 border-2 border-orange-400'
                  : classResult.overall_classification === 'enforcement_discretion'
                  ? 'bg-yellow-100 border-2 border-yellow-400'
                  : 'bg-red-100 border-2 border-red-400'
              }`}>
                <span data-testid="classification-result" className="text-lg font-bold">
                  {classResult.overall_classification === 'non_device_cds' && 'Non-Device CDS (Exempt)'}
                  {classResult.overall_classification === 'enforcement_discretion' && 'Enforcement Discretion (2026 Update)'}
                  {classResult.overall_classification === 'device' && 'Medical Device (Regulated)'}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <CriterionBadge label="Criterion 1: No Image/Signal Processing" result={classResult.criterion_1} />
                <CriterionBadge label="Criterion 2: Medical Information Sources" result={classResult.criterion_2} />
                <CriterionBadge label="Criterion 3: HCP Decision Support" result={classResult.criterion_3} />
                <CriterionBadge label="Criterion 4: Independent Review" result={classResult.criterion_4} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============ INPUTS TAB ============ */}
      {activeTab === 'inputs' && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Input Data Type Taxonomy</h2>
          <p className="text-sm text-gray-600 mb-4">Classify input data types against Criterion 1 (no image/signal/pattern processing).</p>
          <input data-testid="input-taxonomy-field" value={inputTaxonomy} onChange={e => setInputTaxonomy(e.target.value)}
            className="w-full border rounded-md p-2 text-sm mb-3" placeholder="ct_scan, blood_pressure_single, ecg_waveform, medication_list" />
          <button data-testid="classify-inputs-btn" onClick={handleClassifyInputs} disabled={isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {isLoading ? 'Classifying...' : 'Classify Inputs'}
          </button>
          {inputResults.length > 0 && (
            <table className="mt-4 w-full text-sm">
              <thead><tr className="border-b"><th className="text-left py-2">Input</th><th className="text-left py-2">Category</th><th className="text-left py-2">Criterion 1</th></tr></thead>
              <tbody>
                {inputResults.map((r, i) => (
                  <tr key={i} className="border-b">
                    <td className="py-2 font-mono text-xs">{r.input_type}</td>
                    <td className="py-2"><span className={`px-2 py-0.5 rounded text-xs ${r.data_category === 'image' || r.data_category === 'signal' || r.data_category === 'pattern' ? 'bg-red-100 text-red-800' : 'bg-orange-100 text-orange-800'}`}>{r.data_category}</span></td>
                    <td className="py-2">{r.criterion_1_impact === 'pass' ? <CheckCircle className="w-4 h-4 text-orange-600" /> : <XCircle className="w-4 h-4 text-red-600" />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ============ SOURCES TAB ============ */}
      {activeTab === 'sources' && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Data Source Provenance Validation</h2>
          <p className="text-sm text-gray-600 mb-4">Validate that all data sources are "well-understood and accepted" per Criterion 2.</p>
          {sources.map((src, i) => (
            <div key={i} className="flex gap-2 mb-2">
              <input value={src.name} onChange={e => updateSource(i, 'name', e.target.value)}
                className="flex-1 border rounded-md p-2 text-sm" placeholder="Source name" />
              <select value={src.type} onChange={e => updateSource(i, 'type', e.target.value)}
                className="border rounded-md p-2 text-sm">
                {SOURCE_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
              </select>
              {sources.length > 1 && <button onClick={() => removeSource(i)} className="text-red-500 text-sm px-2">Remove</button>}
            </div>
          ))}
          <button onClick={addSource} className="text-blue-600 text-sm mb-3 block">+ Add Source</button>
          <button data-testid="validate-sources-btn" onClick={handleValidateSources} disabled={isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {isLoading ? 'Validating...' : 'Validate Sources'}
          </button>
          {srcValidation && (
            <div className={`mt-4 p-4 rounded-lg ${(srcValidation as { overall_status: string }).overall_status === 'accepted' ? 'bg-orange-50 border border-green-300' : 'bg-red-50 border border-red-300'}`}>
              <div className="flex items-center gap-2 mb-2">
                {(srcValidation as { overall_status: string }).overall_status === 'accepted'
                  ? <CheckCircle className="w-5 h-5 text-orange-600" />
                  : <AlertTriangle className="w-5 h-5 text-red-600" />}
                <span className="font-semibold text-sm">
                  {(srcValidation as { overall_status: string }).overall_status === 'accepted' ? 'All Sources Accepted' : 'Flagged Sources Detected'}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============ LABELING TAB ============ */}
      {activeTab === 'labeling' && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">FDA CDS Labeling Generator</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Product Name</label>
              <input data-testid="product-name" value={productName} onChange={e => setProductName(e.target.value)}
                className="w-full border rounded-md p-2 text-sm" placeholder="e.g., CardioRisk Pro" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Algorithm Summary</label>
              <input value={algoSummary} onChange={e => setAlgoSummary(e.target.value)}
                className="w-full border rounded-md p-2 text-sm" placeholder="e.g., Pooled Cohort Equations" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Target Population</label>
              <input value={targetPop} onChange={e => setTargetPop(e.target.value)}
                className="w-full border rounded-md p-2 text-sm" placeholder="e.g., Adults aged 40-79" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Validation Summary</label>
              <input value={valSummary} onChange={e => setValSummary(e.target.value)}
                className="w-full border rounded-md p-2 text-sm" placeholder="e.g., Validated on 25K patients" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Known Limitations (one per line)</label>
              <textarea value={limitations} onChange={e => setLimitations(e.target.value)}
                className="w-full border rounded-md p-2 text-sm" rows={3} placeholder="Not validated for ages <40&#10;Does not account for novel biomarkers" />
            </div>
          </div>
          <button data-testid="generate-labeling-btn" onClick={handleGenerateLabeling} disabled={isLoading}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {isLoading ? 'Generating...' : 'Generate Labeling'}
          </button>
          {labelResult && (
            <div className="mt-4 bg-gray-50 rounded-lg p-4 space-y-3">
              <div><h3 className="font-semibold text-sm text-gray-800">Intended Use Statement</h3>
                <p className="text-sm text-gray-700 mt-1">{(labelResult as Record<string, string>).intended_use_statement}</p></div>
              <div><h3 className="font-semibold text-sm text-gray-800">Automation Bias Warning</h3>
                <p className="text-sm text-red-700 mt-1 bg-red-50 p-2 rounded">{(labelResult as Record<string, string>).automation_bias_warning}</p></div>
            </div>
          )}
        </div>
      )}

      {/* ============ FULL PACKAGE TAB ============ */}
      {activeTab === 'package' && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Full CDS Compliance Package</h2>
          <p className="text-sm text-gray-600 mb-4">Generate a complete FDA CDS compliance package including classification, labeling, transparency report, and bias assessment. Fill in fields on the other tabs first.</p>
          <button data-testid="generate-package-btn" onClick={handleGeneratePackage} disabled={isLoading}
            className="px-4 py-2 bg-orange-600 text-white rounded-md text-sm font-medium hover:bg-orange-700 disabled:opacity-50">
            {isLoading ? 'Generating...' : 'Generate Full Compliance Package'}
          </button>
          {packageResult && (
            <div className="mt-4 space-y-4">
              <div className={`p-3 rounded-lg text-center text-sm font-bold ${
                (packageResult as { cds_classification: { overall_classification: string } }).cds_classification.overall_classification === 'non_device_cds'
                  ? 'bg-orange-100 text-orange-800' : 'bg-red-100 text-red-800'
              }`}>
                Classification: {(packageResult as { cds_classification: { overall_classification: string } }).cds_classification.overall_classification.replace(/_/g, ' ').toUpperCase()}
              </div>
              <details className="border rounded-lg p-3">
                <summary className="font-semibold text-sm cursor-pointer flex items-center gap-2"><FileText className="w-4 h-4" /> Labeling</summary>
                <pre className="mt-2 text-xs bg-gray-50 p-3 rounded overflow-auto max-h-60">
                  {JSON.stringify((packageResult as Record<string, unknown>).labeling, null, 2)}
                </pre>
              </details>
              <details className="border rounded-lg p-3">
                <summary className="font-semibold text-sm cursor-pointer flex items-center gap-2"><Eye className="w-4 h-4" /> Transparency Report</summary>
                <pre className="mt-2 text-xs bg-gray-50 p-3 rounded overflow-auto max-h-60">
                  {JSON.stringify((packageResult as Record<string, unknown>).transparency_report, null, 2)}
                </pre>
              </details>
              <details className="border rounded-lg p-3">
                <summary className="font-semibold text-sm cursor-pointer flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> Automation Bias Risk</summary>
                <pre className="mt-2 text-xs bg-gray-50 p-3 rounded overflow-auto max-h-60">
                  {JSON.stringify((packageResult as Record<string, unknown>).automation_bias_risk, null, 2)}
                </pre>
              </details>
              <details className="border rounded-lg p-3">
                <summary className="font-semibold text-sm cursor-pointer flex items-center gap-2"><Database className="w-4 h-4" /> Input Taxonomy</summary>
                <pre className="mt-2 text-xs bg-gray-50 p-3 rounded overflow-auto max-h-60">
                  {JSON.stringify((packageResult as Record<string, unknown>).input_taxonomy, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
