# PDF to reviewed flashcards

An owning instructor submits a bounded PDF and requested card count. The API
reserves and uploads; a separate worker extracts, calls Gemini and validates.
No expensive PDF or AI operation runs in the HTTP request.

```mermaid
flowchart TD
  UI["Instructor: PDF, Subject, card target"] --> Reserve["Reserve with stable idempotency key"]
  Reserve --> Upload["Stream-count bytes; validate PDF; encrypt source"]
  Upload --> Duplicate{"Same-Subject Knowledge duplicate?"}
  Duplicate -->|"No"| Queue["Durable queued job"]
  Duplicate -->|"Yes"| Choice["Explicit reuse, separate copy or cancel"]
  Choice -->|"Reuse compatible ready revision"| Queue
  Choice -->|"Separate private copy"| Queue
  Choice -->|"Cancel"| Cancel["End whole job; clean temporary source"]
  Queue --> Worker["Worker claim + lease + claim-token fence"]
  Worker --> Extract["Killable child: page-preserving extraction"]
  Extract -. "Opt-in; no usable native text" .-> OCR["Local OCR"]
  OCR --> Prepared["Trusted page/section/chunk snapshot"]
  Extract --> Prepared
  Prepared -. "RAG enabled and capture requested" .-> Knowledge["Private Knowledge capture + index enqueue"]
  Prepared --> Pipeline["Bounded Gemini pipeline"]
  Pipeline --> Validated["Strict shape, grounding, quality and distinctness"]
  Validated --> Count{"Validated yield"}
  Count -->|"Exact requested target"| Commit["Atomic unpublished set + unapproved cards"]
  Count -->|"Positive count below target"| Stage["Encrypted pending validated-card choice"]
  Count -->|"No valid result / failure"| Failure["Safe terminal failure; retention rules"]
  Stage --> Smaller["Owner confirms exact smaller count"]
  Smaller -->|"No provider request"| Commit
  Stage -->|"Paid manual retry with cost acknowledgment"| Queue
  Stage -->|"Cancel or expire"| Cancel
  Commit --> Review["Instructor edits and approves cards"]
  Review --> Publish["Publish set with at least one approved card"]
  Publish --> Study["Enrolled students study approved cards"]
```

An unchanged explicit Knowledge revision is a no-op. Duplicate reuse does not
capture or embed that revision again. Raw upload accounting still applies.
Knowledge publication is independent of flashcard publication; a flashcard
failure can leave valid private Knowledge. Cancellation never removes an
independent reviewed Knowledge revision.

## Inside the Gemini pipeline

```mermaid
flowchart LR
  Chunks["Server-issued evidence chunks"] --> Preflight["Catalog, tokens, requests, cost and deadline"]
  Preflight --> Packs{"Evidence packs"}
  Packs -->|"One pack"| Generate["Structured card batches"]
  Packs -->|"Multiple packs"| Map["Bounded summaries per pack"]
  Map --> Reduce["Bounded summary reduction"]
  Reduce --> Generate
  Generate --> Validate["Local canonical card + trusted quote/answer checks"]
  Validate --> Dedupe["Quality and duplicate rejection"]
  Dedupe --> Missing{"Missing target cards and budget remains?"}
  Missing -->|"Yes: bounded refill"| Generate
  Missing -->|"No"| Result["Exact result or smaller validated choice"]
  Governor["Worker-wide concurrency / RPM / input TPM"] -. "Every physical provider attempt" .-> Map
  Governor -.-> Reduce
  Governor -.-> Generate
```

Repository default: native Gemini `gemini-3.8-flash`, LOW thinking. The closed
supported catalog is listed in the [visual guide index](README.md#models-and-settings-at-a-glance).
The selected provider/model/catalog/schema policy is frozen on the job;
incompatible workers fail safely rather than substitute a model.

Each accepted card has trimmed nonempty front/back, four unique options and
one matching answer. The verified answer must occur in its trusted exact
quote; the server derives page/section provenance. Model output cannot approve
a card or choose source IDs/configuration. Summaries help planning and do not
replace original evidence.

Generation has one application retry owner: at most three transient retries
with delays of at least three seconds and usable longer `Retry-After`.
SDK retries are disabled. Permanent request/auth/model failures do not retry.
A handled failure or whole-job timeout does not automatically rerun the whole
paid pipeline. Final set/cards/status/source cleanup commit together; a stale
worker cannot commit a partial or duplicate result.

Sources: [generation contract](../architecture/AI-GENERATION-FLOW.md),
[job service](../../backend/app/services/generation.py),
[worker](../../backend/app/workers/generation.py),
[pipeline](../../backend/app/ai/pipeline.py),
[grounding](../../backend/app/ai/grounding.py),
[catalog](../../backend/app/ai/gemini_catalog.py),
[candidate storage](../../backend/app/services/candidate_storage.py),
[job UI](../../frontend/src/components/generation/GenerationJobCard.tsx).
