import { expect, test } from '@playwright/test'

type CapturedMessage = { ID: string; Subject: string; To: { Address: string }[] }

test('real instructor generation, review, publish, emailed invitation and student study persist', async ({ page, request }) => {
  const instructorEmail = process.env.JOURNEY_INSTRUCTOR_EMAIL
  const instructorPassword = process.env.JOURNEY_INSTRUCTOR_PASSWORD
  const studentEmail = process.env.JOURNEY_STUDENT_EMAIL
  const studentPassword = process.env.JOURNEY_STUDENT_PASSWORD
  const mailpitOrigin = process.env.JOURNEY_MAILPIT_ORIGIN
  const pdfFile = process.env.JOURNEY_PDF_FILE
  const appOrigin = process.env.JOURNEY_APP_ORIGIN
  const ragMode = process.env.JOURNEY_RAG_MODE
  if (process.env.RUN_JOURNEY_TESTS !== '1' || !instructorEmail || !instructorPassword
    || !studentEmail || !studentPassword || !mailpitOrigin || !pdfFile || !appOrigin
    || (ragMode !== 'rag-off' && ragMode !== 'rag-on')) {
    throw new Error('Run the journey through scripts/test_journey.py with its disposable runtime')
  }
  const ragEnabled = ragMode === 'rag-on'
  const subjectName = ragEnabled ? 'Journey Biology' : 'Journey RAG Off Biology'
  const errors: string[] = []
  let authorization = ''
  page.on('pageerror', (error) => errors.push(error.name))
  page.on('dialog', (dialog) => { void dialog.accept() })
  page.on('request', (browserRequest) => {
    const candidate = browserRequest.headers().authorization
    if (candidate?.startsWith('Bearer ')) authorization = candidate
  })

  await test.step('operator-created instructor creates a subject and uploads a real PDF', async () => {
    await page.goto('/login')
    await page.getByLabel('Email').fill(instructorEmail)
    await page.getByLabel('Password').fill(instructorPassword)
    await page.getByRole('button', { name: 'Sign In' }).click()
    await expect(page).toHaveURL(/\/dashboard$/)
    await page.getByRole('button', { name: 'New Subject' }).click()
    await page.getByRole('textbox', { name: 'Subject name' }).fill(subjectName)
    await page.getByRole('button', { name: 'Create', exact: true }).click()
    await page.getByRole('link', { name: subjectName }).click()
    await page.getByRole('button', { name: 'Generate Flashcard Set' }).click()
    await page.getByLabel('Set Title').fill('Journey Leaf Facts')
    await page.getByLabel('Number of Cards').fill('2')
    await page.locator('#generation-pdf').setInputFiles(pdfFile)
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

  if (!ragEnabled) {
    await test.step('ordinary generation leaves disabled RAG paths inactive', async () => {
      if (!authorization) throw new Error('The instructor access token was not observed')
      const subjectId = subjectPath.split('/').at(-1)
      if (!subjectId) throw new Error('The generated Subject path was invalid')
      const profileResponse = await request.get(
        `${appOrigin}/api/subjects/${subjectId}/rag/profile`,
        { headers: { Authorization: authorization } },
      )
      expect(profileResponse.ok()).toBe(true)
      const profile = await profileResponse.json() as {
        rag_enabled: boolean
        answer_available: boolean
        embedding_available: boolean
      }
      expect(profile).toMatchObject({
        rag_enabled: false,
        answer_available: false,
        embedding_available: false,
      })
      const threadResponse = await request.post(
        `${appOrigin}/api/subjects/${subjectId}/rag/threads`,
        { headers: { Authorization: authorization } },
      )
      expect(threadResponse.status()).toBe(503)
      await expect(page.getByRole('button', { name: 'Upload to Knowledge' })).toBeDisabled()
      await expect(page.getByRole('button', { name: 'Ask', exact: true })).toBeDisabled()
    })
    expect(errors).toEqual([])
    return
  }

  await test.step('flashcard publication does not unlock Ask AI before separate Knowledge publication', async () => {
    await expect(page.getByText('Awaiting instructor review')).toBeVisible({ timeout: 30_000 })
    const askAi = page.locator('section[aria-labelledby="ask-ai-heading"]')
    await askAi.getByRole('textbox', { name: 'Question' }).fill('What color does chlorophyll give leaves?')
    await askAi.getByRole('button', { name: 'Ask', exact: true }).click()
    await expect(askAi.getByRole('alert')).toContainText(/unavailable|published/i)
    await page.getByRole('button', { name: 'Review & publish' }).click()
    await expect(page.getByText('Published for enrolled students')).toBeVisible()
  })

  let invitationLink = ''
  let secondInvitationLink = ''
  let secondSubjectPath = ''
  await test.step('email outbox worker delivers the invitation through Mailpit', async () => {
    await page.goto('/dashboard')
    await page.getByRole('button', { name: 'New Subject' }).click()
    await page.getByRole('textbox', { name: 'Subject name' }).fill('Journey Boundary Subject')
    await page.getByRole('button', { name: 'Create', exact: true }).click()
    await page.getByRole('link', { name: /Journey Boundary Subject/ }).click()
    secondSubjectPath = new URL(page.url()).pathname
    await page.getByRole('button', { name: 'Invite', exact: true }).click()
    await page.getByRole('button', { name: 'Generate Invite Link' }).click()
    secondInvitationLink = await page.getByLabel('Copyable invitation link').inputValue()
    await page.getByRole('button', { name: 'Close', exact: true }).click()

    await page.goto(subjectPath)
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
    await page.goto(secondInvitationLink)
    await expect(page.getByText('Journey Boundary Subject', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Go to Dashboard' }).click()
    await page.goto(subjectPath)
    const askAi = page.locator('section[aria-labelledby="ask-ai-heading"]')
    await askAi.getByRole('textbox', { name: 'Question' }).fill('What color does chlorophyll give leaves?')
    await askAi.getByRole('button', { name: 'Ask', exact: true }).click()
    await expect(askAi.getByText('Chlorophyll gives leaves their Green color.', { exact: true })).toBeVisible({ timeout: 30_000 })
    await askAi.getByRole('button', { name: /p\.1/ }).click()
    const evidence = page.getByRole('dialog', { name: 'Authorized evidence' })
    await expect(evidence).toContainText('Chlorophyll gives leaves their Green color.')
    await evidence.getByRole('button', { name: 'Close' }).click()
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

  await test.step('a student enrolled in both Subjects cannot cross the RAG Subject boundary', async () => {
    if (!authorization) throw new Error('The student access token was not observed')
    const firstSubjectId = subjectPath.split('/').at(-1)
    const secondSubjectId = secondSubjectPath.split('/').at(-1)
    if (!firstSubjectId || !secondSubjectId) throw new Error('A generated Subject path was invalid')
    const headers = { Authorization: authorization }
    const firstThreadsResponse = await request.get(
      `${appOrigin}/api/subjects/${firstSubjectId}/rag/threads`,
      { headers },
    )
    expect(firstThreadsResponse.ok()).toBe(true)
    const firstThreads = await firstThreadsResponse.json() as { threads: { id: string }[] }
    expect(firstThreads.threads).toHaveLength(1)

    const secondThreadResponse = await request.post(
      `${appOrigin}/api/subjects/${secondSubjectId}/rag/threads`,
      { headers },
    )
    expect(secondThreadResponse.status()).toBe(201)
    const crossSubjectResponse = await request.get(
      `${appOrigin}/api/subjects/${secondSubjectId}/rag/threads/${firstThreads.threads[0].id}`,
      { headers },
    )
    expect(crossSubjectResponse.status()).toBe(404)
  })
  expect(errors).toEqual([])
})
