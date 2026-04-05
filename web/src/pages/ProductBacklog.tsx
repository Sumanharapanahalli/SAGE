import { useState } from 'react'
import { ChevronRight, User, CheckCircle, Clock, AlertTriangle, FileText, Target, Users as UsersIcon } from 'lucide-react'
import { toast } from 'sonner'
import {
  gatherRequirements,
  type ProductOwnerQuestion as Question,
  type ProductOwnerPersona as UserPersona,
  type ProductOwnerUserStory as UserStory,
  type ProductOwnerBacklog as ProductBacklog,
  type RequirementsGatheringResponse as RequirementsGatheringResult
} from '../api/client'

interface QAEntry {
  question: string
  answer: string
  topic: string
}

const priorityColors = {
  'Must Have': 'bg-red-100 text-red-800 border border-red-200',
  'Should Have': 'bg-orange-100 text-orange-800 border border-orange-200',
  'Could Have': 'bg-blue-100 text-blue-800 border border-blue-200',
  'Won\'t Have': 'bg-gray-100 text-gray-800 border border-gray-200'
}

const businessValueColors = {
  'high': 'bg-orange-100 text-orange-800',
  'medium': 'bg-yellow-100 text-yellow-800',
  'low': 'bg-gray-100 text-gray-800'
}

export default function ProductBacklog() {
  const [customerInput, setCustomerInput] = useState('')
  const [result, setResult] = useState<RequirementsGatheringResult | null>(null)
  const [qaHistory, setQaHistory] = useState<QAEntry[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentAnswer, setCurrentAnswer] = useState('')
  const [selectedQuestion, setSelectedQuestion] = useState<Question | null>(null)
  const [activeTab, setActiveTab] = useState('input')

  const handleGatherRequirements = async () => {
    if (!customerInput.trim()) {
      toast.error('Please provide a product description')
      return
    }

    setIsLoading(true)
    try {
      const data = await gatherRequirements({
        customer_input: customerInput,
        follow_up_qa: qaHistory.length > 0 ? qaHistory : undefined
      })
      setResult(data)

      if (data.status === 'complete') {
        setActiveTab('backlog')
        toast.success('Product backlog generated successfully!')
      } else if (data.status === 'needs_clarification') {
        setActiveTab('questions')
        toast.info(`${data.questions?.length || 0} clarifying questions generated`)
      }
    } catch (error) {
      console.error('Error gathering requirements:', error)
      toast.error('Failed to gather requirements')
    } finally {
      setIsLoading(false)
    }
  }

  const answerQuestion = (question: Question) => {
    if (!currentAnswer.trim()) {
      toast.error('Please provide an answer')
      return
    }

    const qaEntry: QAEntry = {
      question: question.question,
      answer: currentAnswer,
      topic: question.topic
    }

    setQaHistory(prev => [...prev, qaEntry])
    setCurrentAnswer('')
    setSelectedQuestion(null)
    toast.success('Answer recorded')
  }

  const continueWithAnswers = async () => {
    if (qaHistory.length === 0) {
      toast.error('Please answer at least one question')
      return
    }

    setIsLoading(true)
    try {
      const data = await gatherRequirements({
        customer_input: customerInput,
        follow_up_qa: qaHistory
      })
      setResult(data)

      if (data.status === 'complete') {
        setActiveTab('backlog')
        toast.success('Product backlog generated successfully!')
      }
    } catch (error) {
      console.error('Error generating backlog:', error)
      toast.error('Failed to generate backlog')
    } finally {
      setIsLoading(false)
    }
  }

  const handoffToSystemsEngineering = () => {
    toast.success('Handoff to Systems Engineering initiated')
  }

  const resetFlow = () => {
    setCustomerInput('')
    setResult(null)
    setQaHistory([])
    setCurrentAnswer('')
    setSelectedQuestion(null)
    setActiveTab('input')
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Product Backlog Management</h1>
          <p className="text-sm text-gray-600 mt-1">
            Transform customer inputs into structured product requirements
          </p>
        </div>
        {result && (
          <button
            onClick={resetFlow}
            className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Start New Product
          </button>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('input')}
            className={`py-2 px-1 border-b-2 font-medium text-sm whitespace-nowrap ${
              activeTab === 'input'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Customer Input
          </button>
          <button
            onClick={() => setActiveTab('questions')}
            disabled={!result?.questions}
            className={`py-2 px-1 border-b-2 font-medium text-sm whitespace-nowrap flex items-center gap-2 ${
              activeTab === 'questions'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } ${!result?.questions ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            Clarifying Questions
            {result?.questions && result.questions.length > 0 && (
              <span className="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full">
                {result.questions.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('backlog')}
            disabled={!result?.backlog}
            className={`py-2 px-1 border-b-2 font-medium text-sm whitespace-nowrap flex items-center gap-2 ${
              activeTab === 'backlog'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } ${!result?.backlog ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            Product Backlog
            {result?.backlog && (
              <span className="bg-orange-100 text-orange-800 text-xs px-2 py-0.5 rounded-full">
                {result.backlog.user_stories.length} stories
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('handoff')}
            disabled={!result?.handoff_ready}
            className={`py-2 px-1 border-b-2 font-medium text-sm whitespace-nowrap ${
              activeTab === 'handoff'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } ${!result?.handoff_ready ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            Systems Handoff
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'input' && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Product Description</h3>
            <p className="text-sm text-gray-600">
              Describe your product idea in natural language. Be as detailed or as brief as you'd like.
            </p>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label htmlFor="customer-input" className="block text-sm font-medium text-gray-700 mb-2">
                What do you want to build?
              </label>
              <textarea
                id="customer-input"
                rows={6}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
                placeholder="I want a fitness app that helps users track their workouts and nutrition..."
                value={customerInput}
                onChange={(e) => setCustomerInput(e.target.value)}
              />
            </div>

            <div className="flex justify-between items-center">
              <div className="text-sm text-gray-500">
                Examples: "I want a meditation app", "Build a project management tool", "Create an e-commerce platform"
              </div>
              <button
                onClick={handleGatherRequirements}
                disabled={isLoading || !customerInput.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? 'Analyzing...' : 'Gather Requirements'}
              </button>
            </div>

            {qaHistory.length > 0 && (
              <div className="mt-4 p-4 bg-blue-50 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">Previous Answers ({qaHistory.length})</h4>
                <div className="space-y-2">
                  {qaHistory.map((qa, index) => (
                    <div key={index} className="text-sm">
                      <div className="font-medium text-blue-800">Q: {qa.question}</div>
                      <div className="text-blue-700">A: {qa.answer}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'questions' && result?.questions && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Clarifying Questions</h3>
            <p className="text-sm text-gray-600">
              Answer these questions to help create a more complete product backlog.
            </p>
          </div>
          <div className="p-6 space-y-4">
            {result.questions.map((question, index) => (
              <div key={index} className="border border-gray-200 rounded-lg p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="font-medium">{question.question}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="inline-flex px-2 py-1 text-xs font-medium bg-gray-100 text-gray-800 rounded">
                        {question.topic}
                      </span>
                      <span className={`inline-flex px-2 py-1 text-xs font-medium rounded ${
                        question.importance === 'high' ? 'bg-red-100 text-red-800' :
                        question.importance === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {question.importance} priority
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedQuestion(question)}
                    className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50"
                  >
                    Answer
                  </button>
                </div>

                {selectedQuestion === question && (
                  <div className="space-y-3 border-t border-gray-200 pt-3">
                    <textarea
                      rows={3}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Your answer..."
                      value={currentAnswer}
                      onChange={(e) => setCurrentAnswer(e.target.value)}
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => answerQuestion(question)}
                        disabled={!currentAnswer.trim()}
                        className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                      >
                        Save Answer
                      </button>
                      <button
                        onClick={() => {
                          setSelectedQuestion(null)
                          setCurrentAnswer('')
                        }}
                        className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {qaHistory.length > 0 && (
              <div className="pt-4 border-t border-gray-200">
                <button
                  onClick={continueWithAnswers}
                  disabled={isLoading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {isLoading ? 'Generating Backlog...' : 'Generate Product Backlog'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'backlog' && result?.backlog && (
        <div className="space-y-6">
          {/* Product Overview */}
          <div className="bg-white shadow rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-orange-500" />
                <h3 className="text-lg font-medium text-gray-900">{result.backlog.product_name}</h3>
              </div>
              <p className="text-gray-600 mt-1">{result.backlog.vision}</p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium mb-2">Target Audience</h4>
                  <p className="text-sm text-gray-600">{result.backlog.target_audience}</p>
                </div>
                <div>
                  <h4 className="font-medium mb-2">Success Metrics</h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                    {result.backlog.success_metrics.map((metric, index) => (
                      <li key={index}>• {metric}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* User Stories */}
            <div className="lg:col-span-2">
              <div className="bg-white shadow rounded-lg">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h3 className="text-lg font-medium text-gray-900">
                    User Stories ({result.backlog.user_stories.length})
                  </h3>
                </div>
                <div className="p-6 space-y-4">
                  {result.backlog.user_stories.map((story) => (
                    <div key={story.id} className="border border-gray-200 rounded-lg p-4 space-y-3">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h4 className="font-medium">{story.title}</h4>
                          <p className="text-sm text-gray-600 mt-1">{story.description}</p>
                        </div>
                        <div className="flex items-center gap-2 ml-4">
                          <span className={`px-2 py-1 text-xs font-medium rounded ${priorityColors[story.priority]}`}>
                            {story.priority}
                          </span>
                          <span className="px-2 py-1 text-xs border border-gray-300 rounded">
                            {story.story_points} pts
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          {story.persona}
                        </span>
                        <span className={`px-2 py-1 rounded ${businessValueColors[story.business_value]}`}>
                          {story.business_value} value
                        </span>
                      </div>

                      <div className="space-y-2">
                        <h5 className="text-sm font-medium">Acceptance Criteria</h5>
                        <ul className="text-sm text-gray-600 space-y-1">
                          {story.acceptance_criteria.map((criteria, index) => (
                            <li key={index} className="flex items-start gap-2">
                              <CheckCircle className="h-4 w-4 text-orange-500 mt-0.5 flex-shrink-0" />
                              {criteria}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {story.dependencies.length > 0 && (
                        <div className="text-xs text-orange-600 flex items-center gap-1">
                          <AlertTriangle className="h-3 w-3" />
                          Depends on: {story.dependencies.join(', ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Sidebar */}
            <div className="space-y-4">
              {/* User Personas */}
              <div className="bg-white shadow rounded-lg">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h3 className="text-lg font-medium text-gray-900">User Personas</h3>
                </div>
                <div className="p-6 space-y-4">
                  {result.backlog.personas.map((persona, index) => (
                    <div key={index} className="border border-gray-200 rounded p-3 space-y-2">
                      <h4 className="font-medium">{persona.name}</h4>
                      <p className="text-sm text-gray-600">{persona.description}</p>
                      <div className="text-xs text-gray-500">
                        Tech comfort: <span className="font-medium">{persona.technical_comfort}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Constraints */}
              <div className="bg-white shadow rounded-lg">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h3 className="text-lg font-medium text-gray-900">Constraints</h3>
                </div>
                <div className="p-6 space-y-4">
                  <div>
                    <h5 className="font-medium text-sm mb-2">Technical</h5>
                    <ul className="text-sm text-gray-600 space-y-1">
                      {result.backlog.technical_constraints.map((constraint, index) => (
                        <li key={index}>• {constraint}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h5 className="font-medium text-sm mb-2">Business</h5>
                    <ul className="text-sm text-gray-600 space-y-1">
                      {result.backlog.business_constraints.map((constraint, index) => (
                        <li key={index}>• {constraint}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'handoff' && result?.backlog && (
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <ChevronRight className="h-5 w-5 text-blue-500" />
              <h3 className="text-lg font-medium text-gray-900">Systems Engineering Handoff</h3>
            </div>
            <p className="text-gray-600 mt-1">
              Ready to convert this product backlog into technical requirements and system architecture.
            </p>
          </div>
          <div className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{result.backlog.user_stories.length}</div>
                <div className="text-sm text-gray-600">User Stories</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">{result.backlog.personas.length}</div>
                <div className="text-sm text-gray-600">User Personas</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">
                  {result.backlog.user_stories.reduce((sum, story) => sum + story.story_points, 0)}
                </div>
                <div className="text-sm text-gray-600">Total Story Points</div>
              </div>
            </div>

            <div className="border-t border-gray-200 pt-6">
              <h4 className="font-medium mb-4">Next Steps in Systems Engineering</h4>
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-3 bg-blue-50 rounded">
                  <div className="w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-xs">1</div>
                  <div>
                    <div className="font-medium">Requirements Derivation</div>
                    <div className="text-sm text-gray-600">Convert user stories to technical system requirements</div>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded">
                  <div className="w-6 h-6 bg-gray-400 text-white rounded-full flex items-center justify-center text-xs">2</div>
                  <div>
                    <div className="font-medium">System Architecture Design</div>
                    <div className="text-sm text-gray-600">Design system architecture with subsystems and interfaces</div>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded">
                  <div className="w-6 h-6 bg-gray-400 text-white rounded-full flex items-center justify-center text-xs">3</div>
                  <div>
                    <div className="font-medium">Risk Assessment</div>
                    <div className="text-sm text-gray-600">Identify and assess system risks and mitigation strategies</div>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded">
                  <div className="w-6 h-6 bg-gray-400 text-white rounded-full flex items-center justify-center text-xs">4</div>
                  <div>
                    <div className="font-medium">V&V Planning</div>
                    <div className="text-sm text-gray-600">Create verification and validation procedures</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-between items-center pt-4 border-t border-gray-200">
              <div className="text-sm text-gray-600">
                Product backlog is ready for systems engineering handoff
              </div>
              <button
                onClick={handoffToSystemsEngineering}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Handoff to Systems Engineering
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}