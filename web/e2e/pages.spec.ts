import { test, expect } from '@playwright/test'

// ---------------------------------------------------------------------------
// Page-specific UI tests — verify key elements render on each page
// Note: Backend API is not running, so we test UI rendering only.
// Pages that fetch data will show loading/empty states — that's fine.
// ---------------------------------------------------------------------------

test.describe('Dashboard', () => {
  test('renders dashboard content', async ({ page }) => {
    await page.goto('/')
    await page.waitForTimeout(500)
    const rootChildren = await page.locator('#root > *').count()
    expect(rootChildren).toBeGreaterThan(0)
  })
})

test.describe('Queue Page', () => {
  test('shows Task Queue heading and stats bar', async ({ page }) => {
    await page.goto('/queue')
    await page.waitForTimeout(1000)
    // The page renders "Task Queue" as an h1
    const content = await page.textContent('body')
    expect(content).toContain('Task Queue')
    // Stats labels
    for (const label of ['Total', 'Pending', 'Completed', 'Failed']) {
      expect(content).toContain(label)
    }
  })

  test('filter pills are rendered', async ({ page }) => {
    await page.goto('/queue')
    await page.waitForTimeout(1000)
    const content = await page.textContent('body')
    // Labels use CSS text-transform uppercase, actual text is lowercase
    expect(content?.toLowerCase()).toContain('status')
    expect(content?.toLowerCase()).toContain('source')
  })
})

test.describe('Goals Page', () => {
  test('shows Goals heading', async ({ page }) => {
    await page.goto('/goals')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content).toContain('Goals')
  })

  test('Add Goal button is present', async ({ page }) => {
    await page.goto('/goals')
    await page.waitForTimeout(500)
    const btn = page.locator('button:has-text("Add Goal")')
    await expect(btn).toBeVisible()
  })

  test('quarter navigation buttons exist', async ({ page }) => {
    await page.goto('/goals')
    await page.waitForTimeout(500)
    // Quarter nav has ‹ and › buttons
    const prevBtn = page.locator('button').filter({ hasText: '‹' })
    const nextBtn = page.locator('button').filter({ hasText: '›' })
    expect(await prevBtn.count()).toBeGreaterThan(0)
    expect(await nextBtn.count()).toBeGreaterThan(0)
  })
})

test.describe('Agent Gym Page', () => {
  test('shows Agent Gym heading and tabs', async ({ page }) => {
    await page.goto('/gym')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content).toContain('Agent Gym')
    // Tabs — check exact text from the component
    expect(content).toContain('Leaderboard')
    expect(content).toContain('Exercise Catalog')
    expect(content).toContain('Train')
    expect(content).toContain('History')
  })

  test('tab switching works', async ({ page }) => {
    await page.goto('/gym')
    await page.waitForTimeout(500)
    const trainTab = page.locator('button').filter({ hasText: 'Train' })
    if (await trainTab.count() > 0) {
      await trainTab.first().click()
      await page.waitForTimeout(200)
      // Train tab should show role input
      const content = await page.textContent('body')
      expect(content).toContain('Role')
    }
  })
})

test.describe('Safety Analysis Page', () => {
  test('shows Safety Analysis heading and tabs', async ({ page }) => {
    await page.goto('/safety')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content).toContain('Safety Analysis')
    expect(content).toContain('FMEA')
    expect(content).toContain('ASIL')
    expect(content).toContain('SIL')
    expect(content).toContain('IEC 62304')
  })

  test('FMEA tab has Add Row button', async ({ page }) => {
    await page.goto('/safety')
    await page.waitForTimeout(500)
    const btn = page.locator('button').filter({ hasText: 'Add Row' })
    await expect(btn.first()).toBeVisible()
  })

  test('ASIL tab shows classification fields', async ({ page }) => {
    await page.goto('/safety')
    await page.waitForTimeout(500)
    // Click ASIL tab
    const asilTab = page.locator('button').filter({ hasText: 'ASIL' })
    await asilTab.first().click()
    await page.waitForTimeout(200)
    const content = await page.textContent('body')
    expect(content).toContain('Severity')
    expect(content).toContain('Exposure')
    expect(content).toContain('Controllability')
  })
})

test.describe('Knowledge Browser Page', () => {
  test('shows Knowledge Base heading and tabs', async ({ page }) => {
    await page.goto('/knowledge')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content).toContain('Knowledge Base')
    expect(content).toContain('Browse')
    expect(content).toContain('Search')
    expect(content).toContain('Add Entry')
  })

  test('Search tab has input', async ({ page }) => {
    await page.goto('/knowledge')
    await page.waitForTimeout(500)
    const searchTab = page.locator('button').filter({ hasText: 'Search' })
    await searchTab.first().click()
    await page.waitForTimeout(200)
    const input = page.locator('input[placeholder*="Search"]')
    await expect(input).toBeVisible()
  })
})

test.describe('Skills & Tools Page', () => {
  test('shows Skills & Tools heading and tabs', async ({ page }) => {
    await page.goto('/skills')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content).toContain('Skills & Tools')
    expect(content).toContain('Skills')
    expect(content).toContain('MCP Tools')
    expect(content).toContain('Runners')
  })

  test('Reload Skills button is present', async ({ page }) => {
    await page.goto('/skills')
    await page.waitForTimeout(500)
    const btn = page.locator('button').filter({ hasText: 'Reload Skills' })
    await expect(btn.first()).toBeVisible()
  })
})

test.describe('Code Execution Page', () => {
  test('shows Code Execution heading and tabs', async ({ page }) => {
    await page.goto('/code')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content).toContain('Code Execution')
    expect(content).toContain('Execute')
    expect(content).toContain('Plan')
    expect(content).toContain('Status')
  })

  test('Execute tab has task textarea and language selector', async ({ page }) => {
    await page.goto('/code')
    await page.waitForTimeout(500)
    const textarea = page.locator('textarea[placeholder*="Describe"]')
    await expect(textarea).toBeVisible()
    const langSelect = page.locator('select')
    await expect(langSelect).toBeVisible()
  })
})

test.describe('Org Graph Page', () => {
  test('renders org graph page content', async ({ page }) => {
    await page.goto('/org-graph')
    await page.waitForTimeout(1000)
    // OrgGraph may show loading, error (no backend), or "Organization" heading
    // Just verify the page renders something
    const content = await page.textContent('body')
    const hasContent = content?.includes('Organization') ||
                       content?.includes('Loading') ||
                       content?.includes('Failed') ||
                       content?.includes('org.yaml')
    expect(hasContent).toBeTruthy()
  })
})

test.describe('Settings Page', () => {
  test('renders settings', async ({ page }) => {
    await page.goto('/settings')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content?.toLowerCase()).toContain('settings')
  })
})

test.describe('LLM Settings Page', () => {
  test('renders LLM content', async ({ page }) => {
    await page.goto('/llm')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    const hasLLM = content?.toLowerCase().includes('llm') || content?.toLowerCase().includes('model')
    expect(hasLLM).toBeTruthy()
  })
})

test.describe('Approvals Page', () => {
  test('renders approvals content', async ({ page }) => {
    await page.goto('/approvals')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content?.toLowerCase()).toContain('approv')
  })
})
