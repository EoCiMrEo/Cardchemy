import { expect, test } from '@playwright/test'

type CapturedMessage = { ID: string; Subject: string; To: { Address: string }[] }

test('real instructor generation, review, publish, emailed invitation and student study persist', async ({ page, request }) => {
  const instructorEmail = process.env.JOURNEY_INSTRUCTOR_EMAIL
  const instructorPassword = process.env.JOURNEY_INSTRUCTOR_PASSWORD
  const studentEmail = process.env.JOURNEY_STUDENT_EMAIL
  const studentPassword = process.env.JOURNEY_STUDENT_PASSWORD
  const mailpitOrigin = process.env.JOURNEY_MAILPIT_ORIGIN
  const pdfFile = process.env.JOURNEY_PDF_FILE
  if (process.env.RUN_JOURNEY_TESTS !== '1' || !instructorEmail || !instructorPassword
    || !studentEmail || !studentPassword || !mailpitOrigin || !pdfFile) {
    throw new Error('Run the journey through scripts/test_journey.py with its disposable runtime')
  }
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.name))
  page.on('dialog', (dialog) => { void dialog.accept() })

  await test.step('operator-created instructor creates a subject and uploads a real PDF', async () => {
    await page.goto('/login')
    await page.getByLabel('Email').fill(instructorEmail)
    await page.getByLabel('Password').fill(instructorPassword)
    await page.getByRole('button', { name: 'Sign In' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)
    await page.getByRole('button', { name: 'New Subject' }).click()
    await page.getByRole('textbox', { name: 'Subject name' }).fill('Journey Biology')
    await page.getByRole('button', { name: 'Create', exact: true }).click()
    await page.getByRole('link', { name: /Journey Biology/ }).click()
    await page.getByRole('button', { name: 'Generate Flashcard Set' }).click()
    await page.getByLabel('Set Title').fill('Journey Leaf Facts')
    await page.getByLabel('Number of Cards').fill('2')
    await page.getByLabel('PDF File').setInputFiles(pdfFile)
    await page.getByRole('button', { name: 'Generate with AI' }).click()
    await expect(page.getByRole('link', { name: 'View & Edit Cards' })).toBeVisible({ timeout: 30_000 })
  })

  const subjectPath = new URL(page.url()).pathname
  await test.step('instructor reviews grounded cards before publishing the set', async () => {
    await page.getByRole('link', { name: 'View & Edit Cards' }).click()
    await expect(page.getByText('Needs Review', { exact: true })).toHaveCount(2)
    await expect(page.getByText(/Verified source.*Page 1/)).toHaveCount(2)
    await page.getByRole('button', { name: 'Approve All' }).click()
    await expect(page.getByText('Approved', { exact: true })).toHaveCount(2)
    await page.goto(subjectPath)
    await page.getByRole('button', { name: 'Edit Journey Leaf Facts' }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByRole('switch', { name: /Published/ }).click()
    await dialog.getByRole('button', { name: 'Save Changes' }).click()
    await expect(dialog).toBeHidden()
    await expect(page.getByText('Published', { exact: true })).toBeVisible()
  })

  let invitationLink = ''
  await test.step('email outbox worker delivers the invitation through Mailpit', async () => {
    await page.getByRole('button', { name: 'Invite', exact: true }).click()
    await page.getByLabel('Student email (optional)').fill(studentEmail)
    await page.getByRole('button', { name: 'Generate and Email Invite' }).click()
    await expect(page.getByRole('dialog').getByRole('status')).toContainText('queued')
    invitationLink = await page.getByLabel('Copyable invitation link').inputValue()
    let captured: CapturedMessage | undefined
    await expect.poll(async () => {
      const response = await request.get(`${mailpitOrigin}/api/v1/messages`)
      const data = await response.json() as { messages: CapturedMessage[] }
      captured = data.messages.find((message) => message.To.some((address) => address.Address === studentEmail))
      return Boolean(captured)
    }, { timeout: 20_000, message: 'Disposable Mailpit must capture the student invitation' }).toBe(true)
    if (!captured) throw new Error('Disposable Mailpit invitation was missing')
    const response = await request.get(`${mailpitOrigin}/api/v1/message/${captured.ID}`)
    const body = await response.json() as { Text: string; HTML: string }
    if (!body.Text.includes(invitationLink) || !body.HTML.includes(invitationLink)) {
      throw new Error('Captured invitation must include the same browser registration link in both parts')
    }
    await page.getByRole('button', { name: 'Close', exact: true }).click()
    await page.goto('/dashboard')
    await page.getByRole('button', { name: 'Logout' }).click()
    await expect(page).toHaveURL(/\/login$/)
  })

  await test.step('student registers through the delivered invitation and studies both cards', async () => {
    await page.goto(invitationLink)
    await expect(page.getByRole('button', { name: 'Create Student Account' })).toBeVisible()
    await page.getByLabel('Full Name').fill('Journey Student')
    await page.getByLabel('Email').fill(studentEmail)
    await page.getByLabel('Password').fill(studentPassword)
    await page.getByRole('button', { name: 'Create Student Account' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await page.getByLabel('Email').fill(studentEmail)
    await page.getByLabel('Password').fill(studentPassword)
    await page.getByRole('button', { name: 'Sign In' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)
    await page.goto(subjectPath)
    await page.getByRole('link', { name: 'Study Now' }).click()
    for (let index = 0; index < 2; index += 1) {
      const question = page.getByRole('heading', { level: 1 })
      await expect(question).toContainText(/chlorophyll|plants/)
      const text = await question.innerText()
      const correctAnswer = text.includes('chlorophyll') ? 'Green' : 'Photosynthesis'
      await page.getByRole('button', { name: new RegExp(correctAnswer) }).click()
      await expect(page.getByText('Correct!', { exact: true })).toBeVisible()
      await page.getByRole('button', { name: 'Next Question' }).click()
    }
    await expect(page.getByRole('heading', { name: 'Session Complete!' })).toBeVisible()
    await page.goto(subjectPath)
    await expect(page.getByText('100% complete', { exact: true })).toBeVisible()
    await expect(page.getByText('0% mastery', { exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Review Again' })).toBeVisible()
  })
  expect(errors).toEqual([])
})
