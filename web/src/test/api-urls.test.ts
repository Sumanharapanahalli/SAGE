import { describe, it, expect, vi, beforeEach } from 'vitest'

// Track all fetch calls
const fetchSpy = vi.fn().mockResolvedValue({
  ok: true,
  json: () => Promise.resolve({}),
  status: 200,
})

vi.stubGlobal('fetch', fetchSpy)

// Import after stubbing fetch
const client = await import('../api/client')

describe('Safety Analysis API URLs', () => {
  beforeEach(() => fetchSpy.mockClear())

  it('runFMEA posts to /api/safety/fmea', async () => {
    await client.runFMEA([{ component: 'X', failure_mode: 'Y', effect: 'Z', severity: 5, occurrence: 3, detection: 3 }])
    expect(fetchSpy).toHaveBeenCalledWith('/api/safety/fmea', expect.objectContaining({ method: 'POST' }))
  })

  it('runFTA posts to /api/safety/fta with tree body', async () => {
    await client.runFTA({ top_event: 'fail', gates: [{ id: 'G1', type: 'OR', inputs: ['a'] }] })
    const [url, opts] = fetchSpy.mock.calls[0]
    expect(url).toBe('/api/safety/fta')
    const body = JSON.parse(opts.body)
    expect(body).toHaveProperty('tree')
    expect(body.tree).toHaveProperty('top_event', 'fail')
  })

  it('classifyASIL posts to /api/safety/asil', async () => {
    await client.classifyASIL('S3', 'E4', 'C3')
    expect(fetchSpy).toHaveBeenCalledWith('/api/safety/asil', expect.objectContaining({ method: 'POST' }))
  })

  it('classifySIL posts to /api/safety/sil with correct field name', async () => {
    await client.classifySIL(1e-7)
    const [url, opts] = fetchSpy.mock.calls[0]
    expect(url).toBe('/api/safety/sil')
    const body = JSON.parse(opts.body)
    expect(body).toHaveProperty('probability_dangerous_failure_per_hour', 1e-7)
    expect(body).not.toHaveProperty('target_failure_rate')
  })

  it('classifyIEC62304 posts to /api/safety/iec62304-class', async () => {
    await client.classifyIEC62304('death_possible')
    expect(fetchSpy).toHaveBeenCalledWith('/api/safety/iec62304-class', expect.objectContaining({ method: 'POST' }))
  })
})

describe('CDS Compliance API URLs', () => {
  beforeEach(() => fetchSpy.mockClear())

  it('classifyCDSFunction posts to /api/cds/classify', async () => {
    await client.classifyCDSFunction({
      function_description: 'test', input_types: ['vitals'], output_type: 'alert',
      intended_user: 'clinician', urgency: 'high', data_sources: [{ name: 'ehr', type: 'database' }],
    })
    expect(fetchSpy).toHaveBeenCalledWith('/api/cds/classify', expect.objectContaining({ method: 'POST' }))
  })
})

describe('Regulatory Compliance API URLs', () => {
  beforeEach(() => fetchSpy.mockClear())

  it('fetchRegulatoryStandards fetches /api/regulatory/standards', async () => {
    await client.fetchRegulatoryStandards()
    expect(fetchSpy).toHaveBeenCalledWith('/api/regulatory/standards')
  })
})
