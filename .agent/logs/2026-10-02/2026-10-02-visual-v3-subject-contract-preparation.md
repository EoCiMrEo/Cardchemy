# Inert visual v3 admission-bound subject contract

## Scope

Prepared the separately versioned [pure visual v3 module](../../../backend/app/ai/source_judgment_visual_v3.py)
and [synthetic contracts](../../../backend/tests/test_source_judgment_visual_v3.py)
under standing authority for aligned Lane 6 completion. The
[literal subject preparation](2026-10-02-literal-subject-context-preparation.md)
provides the generic, independently checked local span resolver. No historical
v1/v2 contract, provider, configuration, worker, service, migration or retained
runtime file was changed here. No key, provider, database or private lecture
transfer occurred. Ask remains disabled; this is not a release or quality pass.

## New pure boundary

- Frozen local message/snapshot dataclasses bind current and preceding message
  IDs, owner/thread/Subject, exact content hashes, corpus revision, embedding
  space, UTC creation/capture/expiry and actual raw-only question clarity.
- The preceding record must be a distinct USER of the same scope, strictly
  earlier than the current question and still unexpired at caller-supplied
  checking time. A later message, equal timestamp, assistant, scope mismatch,
  stale message or malformed metadata rejects before source projection.
- Raw-clear admission rejects any anchor, preceding body or preceding record.
  Its question, candidate parts, prompt and entire provider request remain
  byte-identical to v2. The admitted clarity bit prevents substituting an
  ambiguous raw result after admission.
- Raw-unclear input accepts only the exact literal anchor revalidated against
  the captured preceding-question bytes, current-question hash, grammar,
  offsets and latest-user index. An unresolved or unsafe prior turn yields
  clarification and has no provider request.
- The anchored request preserves the current question and candidate page/image
  parts. It adds only the literal subject and a trusted context-purpose
  statement. No previous question body, assistant content, local identity,
  provenance offsets/hashes, revision or snapshot metadata enters that addition.
  The subject identifies the referent; all factual learning contributions and
  cue judgments must come exclusively from the issued lecture pages/images.

V3 preserves the 4,096 thinking-inclusive output and existing input, PNG,
request-byte, verdict, closed-ID/category and 0–3 unverified-page limits. A
prospective 120-second transport constant is declared only in this new module;
it does not alter the installed sixty-second v6 policy or make an HTTP call.
Embedding remains one unchanged current question. No answer/verifier was added.

## Verification

`venv/Scripts/python.exe -m pytest tests/test_source_judgment_visual_v3.py
tests/test_source_judgment_visual_v2.py tests/test_source_judgment_visual.py
tests/test_source_navigation_context_v1.py tests/test_source_navigation.py
tests/test_navigation_query_candidate.py -q` from `backend`: **320 passed**,
including **73 new visual-v3** and **110 new literal-context** contracts.

Tests cover exact raw-clear wire equality, narrowly projected literal context,
no prior/identity/provenance leakage, immutable local bindings, strict time and
scope, malformed/tampered/missing anchors, admitted-clarity substitution, no
wire on ambiguity, extra byte/token limits, inherited source binding, closed
verdicts, zero answers and thinking-inclusive output. Every input is invented
public test data. No private source-selection score was produced.

Prepared module SHA:
`ca7e5fa90d2ec59b6d98529785e220cde0430e02c1c21ebed78c5e012dfdfe07`.
Prepared test SHA:
`0771819ab07454fd2dfb0e8d9970bc65c73cb68c8537a02d65002dcba0a6606d`.
Independent code review is a separate step after this preparation.

Subsequent independent review found no actionable defect, passed all 183 new
focused context/visual contracts and verified the supplied module/test/aggregate
SHA bindings. Root separately passed the same 183 focused tests. The reviewer
confirmed exact raw-clear v2 bytes, subject-only anchored projection, strict
local snapshot guards, inherited source-ID parsing and no runtime/provider
activation. SQL admission/reauthorization remains the explicit integration
requirement below; no pure test or signed metadata substitutes for it.

## Remaining integration requirements

The pure snapshot does not authorize itself or prove the SQL record was the
immediately preceding USER. Admission must capture that record under the
existing enqueue/thread lock, preserve its ID and exact hash, and repeat
current access, scope, revision, expiry and source checks before worker use.
Do not use execution-time latest history, which can include later queued turns.

A matching immutable runtime successor, schema/transaction/migration coverage,
disposable and retained verification, fresh source-input/roster bindings and
independent actual display/release evidence remain required. Sending the literal
subject or private lecture cues/images still requires its own precise provider
envelope. The old policies, twelve-case gold, reviews, trials and gates remain
unchanged; this module does not activate Ask or close Lane 6.
