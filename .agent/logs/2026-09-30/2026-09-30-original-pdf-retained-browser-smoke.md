# Retained original-PDF browser smoke

Date: 2026-09-30 (America/Chicago). Scope: read-only browser verification of
the retained local Cardchemy installation after the source-only Lane 6 changes.
Starting checkout: `main` at `6c02d6c` with an in-progress working tree.

The existing development Compose containers had exited cleanly. I started
the existing database, API and frontend containers without building images,
changing root `.env`, migrating, or replacing the populated volume. The
database and API reported healthy. The in-app browser retained an authenticated
local session.

On the student Subject page, the Ask controls were disabled with the pause
message visible. I opened the published original PDF for each of the three
attached lectures, Week 2, Week 3 and Week 4. Each dialog advanced from its
loading state to a rendered first page, with PDF navigation and a correct total
page count (33, 42 and 32). A visual capture showed rendered lecture-page text
rather than the extracted-text error fallback. Week 2 advanced to PDF page 2,
then closed; Week 3 and Week 4 opened after the earlier dialog closed. The tab
was kept for subsequent local QA.

This establishes a bounded authenticated browser smoke for the retained PDFs.
It does not establish every page, mobile layout, assistive-technology behavior,
Ask source quality, or a provider run. No question was submitted, no Gemini
request was made, and Ask remained disabled. The existing PDF.js regression
suite and its independent full frontend check are recorded separately in the
same-day stream-navigation log.
