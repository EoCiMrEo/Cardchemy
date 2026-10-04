# Lane 6 navigation-quality diagnostic after cutover

## Scope and authority

The operator approved source-only, original-PDF navigation and asked the team
to evaluate sources without another page-label questionnaire. This record
continues the retained local `0028` cutover. Ask admission stayed disabled.
The populated database, three encrypted original PDFs, root `.env`, and
restore-verified backup were preserved. The stopped GTE listwise candidate
was not rerun, tuned, or integrated. No paid provider request, new Knowledge
index, or database write was made for this diagnostic.

## Frozen inputs and methods

- A new, source-disjoint original-PDF roster was frozen in operating-system
  Temp before any selector result was inspected: 12 questions, four each of
  direct, paraphrase, and follow-up, on 12 visually inspected pages from one
  previously unused 37-page PDF. Roster SHA-256:
  `a43704ecbb9e979cefada0995fd99077e8b759739632a01ab203e5df335ede76`.
  A second reviewer visually confirmed 12/12 gold pages/windows as useful;
  label SHA-256:
  `ab6249dd56fc014452e3e21951d1b2da220dea56e52cc00e3e573bf54621903e`.
  The source is **not published Knowledge**, so this is an offline proxy and
  cannot pass the real Ask release gate. The frozen roster included the
  author's useful labels; second review was not label-blinded.
- The current `source_navigation_v9` selector was run once against an offline
  local-PDF lexical candidate proxy, with no database or model. The result
  was frozen before grading, SHA-256:
  `9b40caabc66e29f13d156d90a4e14783227c968bd36b6203efee56f7ec4ab7d3`.
  A separate visual review of 30 exact displayed windows and 28 distinct
  original pages was frozen at SHA-256:
  `9939eb583d9194db6d6c36c9be752a75545b4edc0b54942d580a9fd958536587`.
- A new provider-free, read-only `v3/v9` diagnostic harness was added in
  `backend/scripts/diagnose_source_navigation.py`, with tests in
  `backend/tests/test_private_source_navigation_diagnostic.py`. It requires
  frozen bytes, an explicit authorized principal/Subject/revision/space,
  one repeatable-read read-only transaction per case, a private Temp output,
  and no AI credential. It calls the current `navigation_query`, authorized
  lexical SQL, neighbor/page loaders, and `select_navigation_pages`, then
  rechecks exact current source slices. It never enqueues an Ask job and does
  not claim in-app PDF route proof. A private page-only roster derived from
  eleven previously owner-reviewed published cases was frozen at SHA-256:
  `fca9588c20997424e716a726beac7a64db7bdde1036b18734db28ca4c8cdd730`.
  Scope was chosen uniquely by the three PDF hashes inside a separate
  read-only one-off backend container. The diagnostic ran in another one-off
  backend container using a hash-matched Temp copy of the script. Runtime
  source hashes for selector, excerpt picker, and retriever matched the
  checkout. No private identifiers, questions, or source text were printed.
  Private observations SHA-256:
  `cfdd67987bfaea8403d8e3684113fc0b4f70b4291f78023c793917a9991f11da`.
  An independent review visually compared all 33 selected windows with
  16 original PDF pages; label SHA-256:
  `6ee7ed942ad01737e709f66b000f9fadd8978db23a07dc9103f75a53c20679a6`.

## Results and diagnosis

| Measure | Exposed published lexical SQL, 11 cases | Fresh unpublished offline proxy, 12 cases |
| --- | ---: | ---: |
| Exact designated gold page in displayed top three | 10/11 | not a database result |
| At least one useful original page in displayed top three | 11/11 | 9/12 |
| Useful first card | 6/11 | 9/12 |
| Strict useful displayed cards | 17/33 | 16/30 |
| Follow-up useful-page hit@3 | 1/1 | 1/4 |

All eleven published gold pages were eligible and present among SQL lexical
candidates; one lost its designated page at selection, but another displayed
page was useful. All 33 displayed published quotes were exact current-source
slices and matched the original PDF page; all 33 current PDF manifests were
present. Of 16 non-sufficient displayed cards, 15 were on the broad topic
without the requested relation and one missed a question condition. None
failed solely because the quote window was shortened; the full page carried
the same grade. Thus the dominant error is candidate ordering/qualification
for the question relation, not extraction or quote truncation.

The fresh proxy missed the approved overall 10/12 and follow-up 3/4 goals.
Its three failed follow-ups arose at distinct stages: one safe local referent
abstention, one lexical candidate miss on an elliptical question, and one
selection of same-term pages from a different architecture despite the useful
page already being a candidate. No failed follow-up was only a window-cutting
error. These diagnoses are proxy-specific; no real hybrid or authenticated
page-open result follows from them.

A local, no-provider preflight of the still-unpublished original PDF found
37 extracted pages, 33 current-policy chunks, about 4,256 estimated input
tokens, and two document-embedding batches at the running batch size of 32.
This is an estimate, not authorization or a billing receipt. The source is
under the configured 512-chunk and index-token bounds.

## Verification, failures, and limits

- `backend/tests/test_private_source_navigation_diagnostic.py`,
  `test_generation_card_choice.py`, and `test_generation_jobs.py`: **38 passed**.
  The new flashcard bridge regression drives nonzero validated cards through
  `GenerationWorker.process_claim` to encrypted pending choice, exact smaller
  confirmation or cancellation, with no partial set or provider replay.
- `test_ai_quality_refinement.py`: **39 passed**. The synthetic replay report
  now describes current adaptive allocation rather than the superseded fixed
  quota behavior; its local long-allocation case completed two cards from two
  raw candidates. This is not real-model teaching-quality evidence.
- Initial local preflight mistakenly invoked the child extractor without a
  Windows multiprocessing main guard. It was stopped and rerun with the
  same bounded synchronous extractor in a standalone process. The first
  diagnostic container failed before execution because Docker Desktop could
  not bind an `E:` file; copying the hash-matched script into the already
  private Temp bind resolved the mount issue. Neither failure invoked AI or
  wrote to the database.
- The published diagnostic measured **lexical fallback only**, and no
  authenticated PDF range request was opened. The fresh source is unpublished
  and its proxy is not production SQL, vector retrieval, or current access.
  Current private evidence is therefore insufficient for Ask activation.
  The one approved public GTE display rule failed earlier; this record does
  not rehabilitate it. Keep `RAG_ASK_ENABLED=false`.

Next work needs a separately approved, bounded plan for current hybrid-query
measurement and a new eligible source-independent holdout. A paid embedding
or indexing run requires its own endpoint/model/price/call/token/time/cost
envelope. Any revised retrieval/selector policy must be frozen before its
new heldout results are inspected and must keep original-PDF/source-only,
authorization, publication, revision, and embedding-space boundaries.
