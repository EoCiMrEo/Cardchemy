# Private v8 twelve-case trial: partial result and HTTP 503 stop

## Scope and preserved starting state

This record reconciles the consumed twelve-case private trial approved through
`call_kgpvUtmVZEewrXYCwCmfxFf6`. It does not authorize a continuation or change
the model, prompt, source labels, policy, runtime settings, or release gate.
The starting checkout was dirty `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`; all existing work was preserved.
The [startup repair and approval](2026-10-03-private-v8-startup-repair-and-renewal.md)
and [independent source review bridge](2026-10-03-private-v8-exact-review-bridge-freeze.md)
remain separate evidence.

## Actual terminal result

The isolated trial passed startup and finished **T01–T07**. The eighth physical
request, **T08**, returned **HTTP 503**, and the dispatcher stopped without an
automatic retry. T09–T12 were not called. The original host, entry, inner claim,
dispatch intents, usage receipts, seven successful source guards, failed T08
receipt, and terminal summary remain intact in the owner-local stage.

- Fixed denominator: **12** questions; valid completed outcomes: **7**.
- Physical source-judgment attempts: **8**; automatic retries: **0**.
- Embedding, answer-model, answer-verifier and database-write calls: **0**.
- Recorded successful usage: **44,710 input tokens** and **9,865 output tokens
  including thinking**.
- Known price-guard subtotal: **USD0.038077**, at USD0.30 input/USD2.50 output
  per million tokens. The failed request's usage/charge is **unknown**; this
  subtotal is not a provider invoice and does not include older unknown fees.

The one-use twelve-call approval is consumed even though the trial stopped
early. Any new physical provider attempt requires a newly approved envelope;
the failed request is not automatically replayed.

## Independent, unchanged-label reconciliation

The offline reconciler verified the exact stage manifest, every input hash,
the before-outcome **signed forty-eight-source review**, successful result
receipts, selected-guard hashes, issued source identities, current revision,
publication/access predicates and original-PDF/page associations. It did not
relabel sources, inspect lecture text for new labels, read configuration or
credentials, call a provider/database, or operate the browser.

Across the seven valid outcomes, **12 references were selected**. The frozen
review rates **11/12** useful (**91.67%**); one selected reference retains its
non-useful label. All **7/7** questions selected a reviewed useful page, including
their designated gold page. These are partial selection metrics, not an actual
browser-display or complete twelve-question quality pass. Five cases are still
failed or unobserved; they cannot disappear from the final denominator.

The ignored page inventory contains only document slots, original page counts,
selected aliases/case IDs, document/revision IDs, page numbers, revision flags
and PDF hashes. It contains no lecture text, question, model response, credential
or identity of a human user. Its **12 unique selected PDF pages** support the
separate rendered-page check through the published-lecture UI. It is not a
browser observation receipt.

## Bound evidence and remaining gate

| Artifact | SHA-256 |
| --- | --- |
| Consumed stage manifest | `d3a1c43820f98abb6d1327a5d617b881cd7ca1acb15701a63e923a36efc70e2c` |
| Unchanged signed source labels | `fa721e2dd48edfafa9dbfcc27c4e051216ab038a8861887e04684c863e70778e` |
| Actual terminal summary | `ad2df93171294d276f85ef042eedc7cb937401d78026f4e540a436f588f94a94` |
| Ignored selected-page inventory | `44303ffbf8f83b691fbb49274612ba5a7f687bcf4fcee382da45023d9652935c` |
| Ignored partial reconciliation | `43478e54715dfedee8d3676781b128efad1eebbce210df3e7f1fd1a88af7364f` |

The reconciliation script initially refused before writing artifacts because
its local signed-review helper name was incorrect. Correcting that helper call
allowed the signed validation and reconciliation to finish; both attempts were
offline and emitted only a fixed content-free phase/status. Neither attempt
consumed provider quota or modified the trial evidence.

Root `.env`, retained data, original PDFs, populated volumes and all earlier
failures were untouched by this work. Ask was not enabled. Completion still
requires the full matching private set, separate exposed-seed/control results,
actual selected-page display observations and the remaining release checks.
No Lane 6 checkbox is closed by this partial result alone.
