import { expect, test } from '@playwright/test'

import { fixtures, installMockApi } from './support/mockApi'

test('validates every local edit branch while preserving all unrelated card actions', async ({ page }) => {
  const api = await installMockApi(page, {
    auth: 'instructor',
    resolver: (call) => {
      if (call.method === 'GET' && call.path === '/subjects/sets/set-1') {
        return { json: fixtures.set }
      }
      if (call.method === 'GET' && call.path === '/flashcards/sets/set-1/cards') {
        return {
          json: [fixtures.cards[0], { ...fixtures.cards[1], is_approved: false }],
        }
      }
      return undefined
    },
  })

  await page.goto('/sets/set-1')
  await page
    .getByRole('button', { name: `Edit ${fixtures.cards[0].front_content}`, exact: true })
    .click()

  await expect(
    page.getByRole('button', { name: `Approve ${fixtures.cards[1].front_content}`, exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: `Edit ${fixtures.cards[1].front_content}`, exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: `Delete ${fixtures.cards[1].front_content}`, exact: true }),
  ).toBeVisible()

  const writesBeforeValidation = api.count('PUT', '/flashcards/card-1')
  await page.getByRole('textbox', { name: 'Front' }).fill('')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Enter a question before saving')
  expect(api.count('PUT', '/flashcards/card-1')).toBe(writesBeforeValidation)

  await page.getByRole('textbox', { name: 'Front' }).fill(fixtures.cards[0].front_content)
  const optionOne = await page.getByRole('textbox', { name: 'Option 1' }).inputValue()
  await page.getByRole('textbox', { name: 'Option 2' }).fill(optionOne.toUpperCase())
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Each answer option must be unique')
  expect(api.count('PUT', '/flashcards/card-1')).toBe(writesBeforeValidation)
})
