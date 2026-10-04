# Current-question context v2 independent review

## Scope and preserved state

Independent bounded review of the inert `source_navigation_context_v2.py`
candidate. The parent owns that module and any future versioned binder/runtime
integration. This review added synthetic boundary tests and a private aggregate
diagnostic; it changed no application module, original question, source label,
previous evaluation, provider ledger, runtime, database, root `.env`, volume or
original PDF. No provider request, API key read, database read/write or image
download occurred.

The previous candidate preparation and independently reviewed source labels
remain frozen. The original two zero-candidate observations are retained as
misses under their original policy. This diagnostic is not a rerun of retrieval
or source selection, and does not establish a release gate.

## Exact input/code bindings

- Original seed preparation: SHA-256
  `bd986c8964b3a86c7813ff2f31625ce84ff30b0a92902163ac1c7aa3331d9ad6`.
- Prior independent source review: SHA-256
  `1d26489a070602023ab9aae217ab99768f3975cf32981e0919329729b2b7401d`.
- Production raw-query source: SHA-256
  `048b217cfc6db58502bbaee311f54f115d954aa4717caf00307442cbd3c2a3a6`.
- Unchanged context v1: SHA-256
  `9f33698075703f2671238539e4a8b33ec8424dbed0d4f2113bb4a225639a3e17`.
- Reviewed inert context v2: SHA-256
  `a106f11a3e1ea0e55aa35c19d49603ac0c3efb349e55a712bd5e1aa212328ba2`.
- New independent synthetic tests: SHA-256
  `add7fd092017ebf8b4278e7b728d1f1a98d5f17a26d344f0a000891f0296f051`.

The private diagnostic verifies these immutable inputs and executes the actual
production raw-query projection plus each context resolver locally. Private
question bodies and identifiers are excluded from this log.

## Findings

For both original clarification rows, the actual raw-only query was already
clear. Context v1 returned `current_question_invalid` because its general
meta-instruction filter matched the ordinary learning verb `ignore`; the
pronoun filter did not match. This was not a dangling subject or missing-source
diagnosis.

The v2 candidate recognizes both original questions as `clear_current_question`
using that exact raw-only result. Both original question SHA-256 values remain
equal to the frozen review inputs. There are zero new literal anchors, question
rewrites or newly eligible history transfers. The unresolved raw-query branch
delegates to v1 unchanged. No retrieval/display observation has been replaced.

The repair is narrowly scoped to an interrogative current question whose only
v1 meta-filter matches are the literal word `ignore`. It retains text bounds,
control-character, explicit instruction/prompt/credential markers, sentence
shape, exact raw-query equality and digest safeguards. A supplied rewritten
query or invalid raw-query type does not establish the clear branch.

## Independent verification

From `backend`:

```powershell
venv\Scripts\python.exe -m pytest -q tests/test_source_navigation_context_v2.py tests/test_source_navigation_context_v2_independent_review.py tests/test_source_navigation_context_v1.py
```

Result: **168 passed in 1.45 seconds**: 20 parent candidate tests, 38 new
independent boundary tests, and 110 existing v1 tests. Independent cases cover
interrogative variants, compound targets, unchanged hashes, leading imperatives,
explicit prompt/credential/meta markers, appended imperative markers, multiple
questions, Unicode/control characters, punctuation, invalid types, rewritten
raw queries and unchanged unresolved follow-up eligibility.

The exclusive new private diagnostic is in the pre-existing private review
directory under the filename `context-v2-review-diagnostic.json`, SHA-256
`1d4437ef2684557f3fb343ec5fc4c4f616ba4b8646b9104b25b67b47e87dcc84`.
It records: 2/2 actual raw queries resolved; 2/2 old refusals; 2/2 new clear
current questions; 2/2 original hashes preserved; zero anchors/provider calls/
database reads/writes; runtime unchanged; release gate false.

## Limits and next boundary

This grammar/lexical gate is not a complete semantic-clarity or prompt-injection
classifier. Separate synthetic probes found that a generic interrogative with
no named learning subject, and interrogative-shaped questions containing an
embedded imperative without the explicit blocked markers, can remain raw-clear.
The v2 lexical exception accepts such an `ignore` form; equivalent questions
using a non-blacklisted verb were already accepted by v1. Therefore this review
does **not** claim that every imperative embedded in a question is rejected.
All question/source text must remain untrusted, and authorization, bounded
issued-ID validation and source selection must remain independent of clarity.

The candidate remains inert. A future integration must bind and recheck the
actual raw-only query under a new versioned policy, preserve preceding-message
identity/order checks, and rerun actual candidate preparation and release
measurements. This review alone does not repair the frozen retrieval misses or
permit Ask enablement.
