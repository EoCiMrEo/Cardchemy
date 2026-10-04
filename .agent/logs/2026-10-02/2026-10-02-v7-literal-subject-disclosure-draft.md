# Prospective v7 literal-subject disclosure and frontend contract

## Scope and observation

Read-only audit of the current typed RAG profile, profile router, English
catalog, Ask panel and their component/browser/backend contract tests. This
draft records the minimal changes needed when the pure literal-subject/visual
v3 contract is integrated as a prospective navigation v7 policy. It does not
change an existing frontend/backend file, consumed provider-code binding,
runtime flag, root configuration, database or historical evidence. No provider
request, key read, private source read or new quality measurement occurred.

Current source uses navigation v6/visual v2. The typed profile has no literal
subject capability, and `AskAiPanel` fences search and manual retry to v6.
Current visual disclosure says earlier chat is not sent. That wording remains
correct for the old wire; a future v7 wire may contain a literal subject from
the immediately preceding user turn, so it needs an explicit separate
disclosure before first submission and before every paid manual retry.

The [pure context preparation](2026-10-02-private-v6-independent-review-recovery.md)
does not establish authoritative admission/database ordering or enablement.
Public terminal quality, independent private display/usefulness, exact transfer
authorization and release gates remain separate. Retained Ask/source judging
remain disabled; this draft is not an activation instruction.

## Exact minimal contract changes

| Owner/path | Required change |
| --- | --- |
| [Backend profile schema](../../../backend/app/schemas/rag.py) | Add navigation v7 to the applicable profile/job policy literals. Add non-secret `source_judge_transfers_literal_subject_context: bool = False` to `RagProfileResponse`; do not add a prior subject, message body, subject hash or provenance IDs to the HTTP profile. |
| [Profile router](../../../backend/app/routers/rag.py) | Report the capability true only for the implemented v7/visual-v3 contract; false for historical policies. Include v7 in the visual metadata path. Keep Subject authorization before space/profile disclosure, the active-space requirement, `answer_available=False` and independently computed default-off Ask/source-judge availability. Capability describes the possible transfer even while the runtime is paused. |
| [Typed frontend contracts](../../../frontend/src/services/types.ts) | Add v7 to both `RagProfile.ask_policy` and `RagAnswerJob.ask_policy`. Add the required Boolean field to `RagProfile`, update typed fixtures, and use no `any` or assertion to hide missing fields. A missing/unexpected capability must not authorize search. |
| [Ask panel](../../../frontend/src/components/rag/AskAiPanel.tsx) | Compare the capability in `sameProcessorProfile`; require v7 + visual-v3 + capability true + existing enabled/available/image/HIGH flags before new search. Include v7 in disclosure selection. Gate retry to the matching v7 job only; historical v6 and older references remain readable without replaying them under the new policy. Keep profile refresh before both initial enqueue and retry confirmation. |
| [English catalog](../../../frontend/src/i18n/en.ts) | Add separate v7 subject-context search and manual-retry strings. Preserve the old strings for historical profiles. Include at most one unchanged current-question embedding, at most one page-selection request, the optional bounded literal subject, no full earlier questions/history/assistant answers/PDF file bytes, no generated answer, unverified reading suggestions, retention and possible additional retry cost. |

The capability field must correspond to the actual supported request path. A
front-end check is an additional UX fence; it cannot replace backend policy,
admission identity, source scope or provider-spending authorization. No new
user-managed setting or component `.env` file is required for disclosure.

## Proposed product copy

Search disclosure, with providers/models and retention days substituted from
the authorized non-secret profile:

> Before searching: your current question may be sent to Google Gemini API
> for one query embedding. Your current question, selected published page text
> and full-page PNG images may be sent to Google Gemini API in at most one
> request to select related lecture pages. For an unclear follow-up, a literal
> subject of at most 160 characters from the immediately preceding user
> question in this conversation may accompany the page-selection request.
> Full earlier questions, chat history, assistant answers and original PDF file
> bytes are not sent. Gemini returns only page labels and IDs, with no generated
> answer. Selected pages are unverified reading suggestions. Private questions
> are retained for up to [profile retention] days.

Manual retry disclosure uses the same scope, adds that a new query embedding
and page-selection request may incur additional cost, and requires explicit
confirmation. Keep the separate existing estimated additional-cost field and
either the recorded previous cost or **Previous attempt cost is unknown**.
The literal subject accompanies only the source-ID judgment; the embedding
always receives the unchanged current question. The browser must not extract
or send a prior subject/history itself.

## Required verification when implemented

- Backend profile units in a new v7-specific file: capability true only for
  v7/visual-v3 and false for v1–v6; wrong Subject denied before profile/space
  read; mismatching space and paused release keep Ask/source judge unavailable;
  no key/message/history/provenance fields in serialized profile. Update the
  existing exact profile response contract in `test_rag_answers.py`.
- Add a new focused component file for v7 rather than rewriting historical
  disclosure expectations: an enabled consistent v7 profile shows optional
  160-character/latest-user transfer, one current-question embedding, one
  source-ID call, no generated answer and no full-history transfer. Raw-clear
  questions see the capability disclosure but never cause the browser to
  construct or send context.
- Fail closed on false/missing capability, visual-v2/wrong contract, LOW,
  missing image transfer, unavailable profile or disabled Ask. Saved references
  remain readable. A historical v6 failed job has no retry control under v7
  even if its old `can_retry` flag is true.
- Change the capability between initial profile and pre-submit refresh;
  verify the existing `profileChanged` feedback, updated disclosure and zero
  enqueue. Repeat between opening retry confirmation and confirming; verify
  zero retry request. Preserve draft question and idempotency identity.
- V7 retry dialog: the new transfer scope plus possible additional cost is
  visible before `retryJob`; unknown previous spend uses the existing explicit
  unknown-cost string; no raw provider exception is rendered. Cancel and close
  issue zero retry calls. Only explicit confirm may dispatch once.
- Update canonical browser mock profile and the v7 browser fixtures in
  `frontend/e2e/support/mockApi.ts` and `frontend/e2e/rag-knowledge.spec.ts`;
  keep historical profiles explicit with capability false. Browser coverage
  should verify disabled controls, visible pre-use/retry disclosure, matching
  policy retry, refresh fencing and keyboard dialog operation. Existing
  original-PDF opening, access revocation, no-match/clarification and related
  passage semantics remain unchanged.
- Run targeted component/backend contracts during integration, then the
  required full frontend `npm run check` and relevant backend/journey/release
  gates. Existing mock behavior is not provider or private-data validation.

## Draft verification and limits

Only this new log was written. Its local links and whitespace were checked;
no frontend test or build is claimed for an unimplemented disclosure change.
Existing authoritative profile/code tests were inspected without running
live providers or mutating data. The old consumed source/pilot code and signed
review artifacts remain unchanged. Integration and activation remain owned by
the main Lane 6 task after the independent public terminal result.
