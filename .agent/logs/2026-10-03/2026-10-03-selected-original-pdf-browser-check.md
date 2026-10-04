# Selected original PDF pages: retained browser check

## Scope and current state

The root used the authenticated local Cardchemy app in the Codex in-app browser
to inspect the original PDFs associated with the two partial private trials.
The matching packaged frontend remains image
`sha256:e672a910c14e69f68fcecd974fac4435c258c0d12fcdbefca2b46889767ef694`.
Ask and source judging remain disabled. No question submission, provider call,
database write, environment edit or service replacement occurred.

The independent partial inventories bind twelve private-holdout pages and
eight exposed-seed pages. Two overlap, so the browser check covers **18 unique
physical pages across all three published original PDFs**. Document identity
was matched by the visible published catalog and original page counts, then
the physical page status and rendered slide were checked. No private question,
lecture text, UUID or raw response is included in this tracked record.

## Observed results and limits

All eighteen pages rendered a visible PDF canvas at the expected physical page
and page count. None showed the reported original-PDF failure or an extracted
text fallback. Three pages were opened directly through published search
results; the remaining fifteen used the original viewer's previous/next
navigation, checking the updated status after each action. This also exercised
first/last-page navigation bounds and continued authenticated archive reads.

Escape closed the final dialog, removed its canvas, and returned focus to the
exact triggering source button. A read-only DOM observation confirmed zero
remaining dialogs/canvases. The original-PDF rendering defect is not reproduced
on this matching retained frontend.

These are actual **published-browser physical-page observations**, not a claim
that selected Ask jobs were persisted or their reference buttons were clicked.
Adjacent navigation retains the opened reference's extracted text; it does not
prove the selected page's exact quote was displayed next to that page. Exact
quote/reference association and complete Ask display still require their
separate matching component/backend evidence. No provider outcome, review label
or release gate was changed by this check.

The ignored metadata-only witness is
`.agent/.verification/private-selected-pdf-browser-witness-20261003.json`.
It binds both unchanged inventories, distinguishes direct/adjacent routes,
records physical-page rendering and keyboard focus, and explicitly leaves
actual Ask-card/adjacent-selected-quote observations false. The browser's
temporary screenshots were used for visual inspection; lecture content is not
copied into tracked evidence.

The two private trials remain incomplete after their separately recorded HTTP
503 stops. Preserve their successful results, failed attempts and unknown
charges. A new provider continuation needs its own concrete approved envelope;
these browser checks neither consume nor renew that authority.
