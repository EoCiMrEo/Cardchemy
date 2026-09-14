# AI generation quality and safety

The generation worker treats extracted document text as untrusted input. It
never lets document content choose tools, configuration, prompts, provider
settings, output structure, or source metadata.

## Pipeline

1. PDF extraction returns ordered pages rather than one flattened string.
2. Pages are split at headings and paragraphs into token-bounded chunks. Every
   chunk has a server-issued identifier and retains its page and section.
3. The worker builds a complete token and configured-cost estimate before the
   first provider request. Jobs that cannot fit the configured context, job, or
   cost budget fail without calling a provider.
4. Map summaries cover every chunk. Longer documents are reduced in bounded
   levels until one global summary remains; no first-page or first-character
   shortcut is used.
5. A largest-remainder allocation assigns a global card quota to chunks. The
   quotas sum to the requested card count, including when there are more chunks
   than cards.
6. Provider-native JSON Schema output is parsed again by strict server-side
   Pydantic contracts. Unknown fields, coercions, missing options, or malformed
   values are rejected.
7. Candidates name a server-issued chunk and provide an exact source quote.
   The server derives page and section metadata from the trusted chunk, verifies
   the normalized quote and answer against that content, and applies the
   canonical four-option card rules.
8. A deterministic second pass scores clarity and grounding, rejects near
   duplicates using normalized token and character similarity, and performs
   bounded refill calls when candidates are rejected.
9. A successful job persists exactly the requested count. If the provider
   cannot supply enough distinct grounded cards within the refill and budget
   limits, the job fails atomically with no partial set.
10. Every generated card starts in `Needs review`. Model output never approves
    a card; only an explicit instructor action can do that.

## Prompt-injection boundary

System instructions and document data are separate provider messages. Document
chunks and summaries are JSON encoded and labelled as untrusted evidence. The
system instruction explicitly forbids following commands, role changes,
requests for secrets, or output-format instructions found in that evidence.

This boundary is defense in depth. Persistence still depends on strict schema,
server-owned chunk identifiers, exact grounding, canonical option validation,
duplicate checks, and atomic database validation—not on provider obedience.

## Failure behavior

- Summary map or reduce failures use `summary_generation_failed`, remain
  visible on the job, and retain the encrypted source for the configured retry
  period.
- Invalid structured output uses `invalid_generated_cards`; invalid values are
  never truncated or coerced into valid cards.
- Exhausted refill attempts use `insufficient_grounded_cards` and persist no
  partial flashcard set.
- Preflight token/context/cost refusals use stable limit-reason codes, make no
  provider request, and remain visible in the job API and instructor UI.
- Provider timeouts, rate limits, and temporary service failures use bounded
  retries and the durable worker retry policy. Authentication and capability
  errors are permanent until configuration changes.

## Usage and cost

Token counts reported by a provider are stored separately from conservative
estimates. Monetary values use integer micro-US-dollars and operator-supplied
per-million-token rates; the application does not embed a pricing table that
can silently become stale. A zero/unconfigured rate still enforces token
budgets, but its monetary estimate is labelled unavailable.

