import { TrendingUp } from 'lucide-react'

interface FitnessChartProps {
  experimentId: string
}

// Mock data for development - replace with real API call later
const generateMockData = () => {
  const data = []
  let fitness = 0.2
  for (let i = 0; i <= 10; i++) {
    // Simulate gradual improvement with some noise
    fitness += (Math.random() - 0.3) * 0.1 + 0.05
    fitness = Math.max(0, Math.min(1, fitness)) // Clamp between 0 and 1
    data.push({
      generation: i,
      fitness: Math.round(fitness * 1000) / 1000 // Round to 3 decimal places
    })
  }
  return data
}

export default function FitnessChart({ experimentId }: FitnessChartProps) {
  const data = generateMockData()

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <TrendingUp className="h-8 w-8 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-400 text-sm">No fitness data available</p>
        </div>
      </div>
    )
  }

  // Calculate chart dimensions and scaling
  const width = 600
  const height = 256
  const padding = 40
  const chartWidth = width - (padding * 2)
  const chartHeight = height - (padding * 2)

  const minFitness = Math.min(...data.map(d => d.fitness))
  const maxFitness = Math.max(...data.map(d => d.fitness))
  const fitnessRange = maxFitness - minFitness || 0.1 // Avoid division by zero

  const maxGeneration = Math.max(...data.map(d => d.generation))

  // Create path for the fitness line
  const pathPoints = data.map((point, index) => {
    const x = padding + (index / maxGeneration) * chartWidth
    const y = padding + chartHeight - ((point.fitness - minFitness) / fitnessRange) * chartHeight
    return `${x},${y}`
  })
  const path = `M ${pathPoints.join(' L ')}`

  return (
    <div className="w-full">
      <svg width={width} height={height} className="w-full h-64">
        {/* Background grid lines */}
        <defs>
          <pattern id="grid" width="50" height="40" patternUnits="userSpaceOnUse">
            <path d="M 50 0 L 0 0 0 40" fill="none" stroke="#374151" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* Axes */}
        <line
          x1={padding}
          y1={height - padding}
          x2={width - padding}
          y2={height - padding}
          stroke="#6b7280"
          strokeWidth="1"
        />
        <line
          x1={padding}
          y1={padding}
          x2={padding}
          y2={height - padding}
          stroke="#6b7280"
          strokeWidth="1"
        />

        {/* Y-axis labels (fitness values) */}
        <text
          x={padding - 5}
          y={padding + 5}
          fill="#9ca3af"
          fontSize="12"
          textAnchor="end"
        >
          {maxFitness.toFixed(3)}
        </text>
        <text
          x={padding - 5}
          y={padding + chartHeight / 2 + 5}
          fill="#9ca3af"
          fontSize="12"
          textAnchor="end"
        >
          {((maxFitness + minFitness) / 2).toFixed(3)}
        </text>
        <text
          x={padding - 5}
          y={height - padding + 5}
          fill="#9ca3af"
          fontSize="12"
          textAnchor="end"
        >
          {minFitness.toFixed(3)}
        </text>

        {/* X-axis labels (generations) */}
        <text
          x={padding}
          y={height - padding + 20}
          fill="#9ca3af"
          fontSize="12"
          textAnchor="middle"
        >
          Gen 0
        </text>
        <text
          x={width - padding}
          y={height - padding + 20}
          fill="#9ca3af"
          fontSize="12"
          textAnchor="middle"
        >
          Current
        </text>

        {/* Fitness progression line */}
        <path
          d={path}
          fill="none"
          stroke="#3b82f6"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Data points */}
        {data.map((point, index) => {
          const x = padding + (index / maxGeneration) * chartWidth
          const y = padding + chartHeight - ((point.fitness - minFitness) / fitnessRange) * chartHeight
          return (
            <circle
              key={index}
              cx={x}
              cy={y}
              r="3"
              fill="#3b82f6"
            />
          )
        })}
      </svg>

      {/* Legend */}
      <div className="mt-4 text-center">
        <div className="inline-flex items-center gap-2 text-sm text-gray-400">
          <div className="w-3 h-0.5 bg-blue-500"></div>
          <span>Best Fitness Over Time</span>
        </div>
      </div>
    </div>
  )
}