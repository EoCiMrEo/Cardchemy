import AxeBuilder from '@axe-core/playwright'
import { expect } from '@playwright/test'
import type { Page } from '@playwright/test'

const BLOCKING_IMPACTS = new Set(['serious', 'critical'])

export async function expectNoSeriousOrCriticalViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()

  const violations = results.violations
    .filter((violation) => violation.impact && BLOCKING_IMPACTS.has(violation.impact))
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      help: violation.help,
      nodes: violation.nodes.map((node) => ({
        target: node.target.join(' '),
        html: node.html,
        failureSummary: node.failureSummary,
      })),
    }))

  expect(
    violations,
    `Expected no serious/critical accessibility violations:\n${JSON.stringify(violations, null, 2)}`,
  ).toEqual([])
}

export async function expectNoNestedInteractiveControls(page: Page): Promise<void> {
  const nested = page.locator([
    'a button',
    'a input',
    'a select',
    'a textarea',
    'a [role="button"]',
    'button a',
    'button input',
    'button select',
    'button textarea',
    'button [role="button"]',
  ].join(', '))

  await expect(nested, 'Links and buttons must not contain another interactive control').toHaveCount(0)
}

export async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))

  expect(dimensions.scrollWidth, `Horizontal overflow: ${JSON.stringify(dimensions)}`).toBeLessThanOrEqual(
    dimensions.clientWidth + 1,
  )
}

export async function expectMinimumTouchTarget(
  page: Page,
  selector: string,
  minimumCssPixels = 44,
): Promise<void> {
  const target = page.locator(selector)
  await expect(target).toBeVisible()
  const box = await target.boundingBox()
  expect(box, `Expected a measurable touch target for ${selector}`).not.toBeNull()
  expect(box?.width ?? 0, `${selector} is narrower than ${minimumCssPixels}px`).toBeGreaterThanOrEqual(
    minimumCssPixels,
  )
  expect(box?.height ?? 0, `${selector} is shorter than ${minimumCssPixels}px`).toBeGreaterThanOrEqual(
    minimumCssPixels,
  )
}
