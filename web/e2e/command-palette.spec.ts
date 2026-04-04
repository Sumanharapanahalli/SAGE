import { test, expect } from '@playwright/test'

test.describe('Command Palette', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForTimeout(500)
  })

  test('opens with Ctrl+K', async ({ page }) => {
    await page.keyboard.press('Control+k')
    await page.waitForTimeout(200)
    // Palette should be visible — look for the input
    const input = page.locator('input[placeholder*="Go to"]')
    await expect(input).toBeVisible()
  })

  test('closes with Escape', async ({ page }) => {
    await page.keyboard.press('Control+k')
    await page.waitForTimeout(200)
    const input = page.locator('input[placeholder*="Go to"]')
    await expect(input).toBeVisible()
    await page.keyboard.press('Escape')
    await page.waitForTimeout(200)
    await expect(input).not.toBeVisible()
  })

  test('filters results by typing', async ({ page }) => {
    await page.keyboard.press('Control+k')
    await page.waitForTimeout(200)
    const input = page.locator('input[placeholder*="Go to"]')
    await input.fill('chat')
    await page.waitForTimeout(100)
    // Should show Chat result
    const results = page.locator('[class*="palette-result"]')
    const count = await results.count()
    expect(count).toBeGreaterThan(0)
    // At least one result should contain "Chat"
    const text = await page.textContent('[class*="palette-box"]')
    expect(text?.toLowerCase()).toContain('chat')
  })

  test('navigates on Enter', async ({ page }) => {
    await page.keyboard.press('Control+k')
    await page.waitForTimeout(200)
    const input = page.locator('input[placeholder*="Go to"]')
    await input.fill('chat')
    await page.waitForTimeout(100)
    await page.keyboard.press('Enter')
    await page.waitForTimeout(300)
    expect(page.url()).toContain('/chat')
  })

  test('shows all route groups', async ({ page }) => {
    await page.keyboard.press('Control+k')
    await page.waitForTimeout(200)
    const text = await page.textContent('[class*="palette-box"]')
    for (const group of ['WORK', 'INTELLIGENCE', 'KNOWLEDGE', 'ADMIN']) {
      expect(text).toContain(group)
    }
  })

  test('arrow keys move cursor', async ({ page }) => {
    await page.keyboard.press('Control+k')
    await page.waitForTimeout(200)
    // First result should be active
    const firstResult = page.locator('[class*="palette-result"]').first()
    await expect(firstResult).toHaveClass(/active/)
    // Arrow down should move active state
    await page.keyboard.press('ArrowDown')
    await page.waitForTimeout(100)
    const secondResult = page.locator('[class*="palette-result"]').nth(1)
    await expect(secondResult).toHaveClass(/active/)
  })
})
