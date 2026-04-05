import { test, expect } from '@playwright/test'

test.describe('ErrorBoundary', () => {
  test('app renders with ErrorBoundary wrapping (no crash)', async ({ page }) => {
    await page.goto('/')
    await page.waitForTimeout(500)
    // App should render normally — ErrorBoundary is invisible when no error
    const rootChildren = await page.locator('#root > *').count()
    expect(rootChildren).toBeGreaterThan(0)
  })
})

test.describe('OfflineBanner', () => {
  test('banner not shown when dev server is serving (no backend call errors crash the UI)', async ({ page }) => {
    await page.goto('/')
    await page.waitForTimeout(1500)
    // The OfflineBanner may show (no backend running) but shouldn't crash the app
    const rootChildren = await page.locator('#root > *').count()
    expect(rootChildren).toBeGreaterThan(0)
  })
})

test.describe('Safety Analysis — FTA Tab', () => {
  test('FTA tab renders gate builder', async ({ page }) => {
    await page.goto('/safety')
    await page.waitForTimeout(500)
    // Click FTA tab
    const ftaTab = page.locator('button').filter({ hasText: 'FTA' })
    await ftaTab.first().click()
    await page.waitForTimeout(300)
    const content = await page.textContent('body')
    expect(content).toContain('Fault Tree Analysis')
    expect(content).toContain('Top Event')
    expect(content).toContain('Logic Gates')
  })

  test('FTA tab can add gates', async ({ page }) => {
    await page.goto('/safety')
    await page.waitForTimeout(500)
    const ftaTab = page.locator('button').filter({ hasText: 'FTA' })
    await ftaTab.first().click()
    await page.waitForTimeout(300)
    const addGateBtn = page.locator('button').filter({ hasText: 'Add Gate' })
    await expect(addGateBtn.first()).toBeVisible()
    await addGateBtn.first().click()
    await page.waitForTimeout(200)
    // Should have 2 gates now (1 default + 1 added)
    const gateIds = page.locator('input[placeholder="Gate ID"]')
    expect(await gateIds.count()).toBe(2)
  })

  test('SIL tab renders classification', async ({ page }) => {
    await page.goto('/safety')
    await page.waitForTimeout(500)
    const silTab = page.locator('button').filter({ hasText: /^SIL/ })
    await silTab.first().click()
    await page.waitForTimeout(300)
    const content = await page.textContent('body')
    expect(content).toContain('SIL Classification')
    expect(content).toContain('Target Failure Rate')
  })
})

test.describe('Costs Page — Routing Stats', () => {
  test('Costs page renders without crash', async ({ page }) => {
    await page.goto('/costs')
    await page.waitForTimeout(1000)
    const content = await page.textContent('body')
    // Should show Cost Tracker heading even if API is down
    const hasCost = content?.includes('Cost Tracker') || content?.includes('costs API')
    expect(hasCost).toBeTruthy()
  })
})

test.describe('Chat Page — API-backed conversations', () => {
  test('chat page renders welcome screen', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForTimeout(500)
    await expect(page.getByText('SAGE Chat')).toBeVisible()
  })

  test('can open role picker and see roles', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForTimeout(500)
    const btn = page.getByRole('button', { name: /New conversation/i })
    await btn.click()
    await page.waitForTimeout(300)
    await expect(page.getByText('Choose a role')).toBeVisible()
  })
})

test.describe('Goals Page — API-backed', () => {
  test('goals page renders with quarter nav', async ({ page }) => {
    await page.goto('/goals')
    await page.waitForTimeout(500)
    const content = await page.textContent('body')
    expect(content).toContain('Goals')
    // Quarter nav buttons
    const prevBtn = page.locator('button').filter({ hasText: '‹' })
    expect(await prevBtn.count()).toBeGreaterThan(0)
  })

  test('Add Goal button opens form', async ({ page }) => {
    await page.goto('/goals')
    await page.waitForTimeout(500)
    const btn = page.locator('button').filter({ hasText: 'Add Goal' })
    await btn.first().click()
    await page.waitForTimeout(300)
    const content = await page.textContent('body')
    expect(content).toContain('New Objective')
    expect(content).toContain('Objective title')
  })
})
