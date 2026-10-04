# Inert literal preceding-user subject context

## Scope and preservation

Continued authorized Lane 6 preparation on dirty `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. Read repository guidance,
orientation/maps, current source-navigation architecture/ADR and the actual
private hybrid result. Preserved the frozen twelve cases, all gold/source and
vector packets, historical policies and provider trials. This work changes only
the new [pure helper](../../../backend/app/ai/source_navigation_context_v1.py)
and [invented public contracts](../../../backend/tests/test_source_navigation_context_v1.py).
It is detached from runtime; Ask remains disabled. No provider, credential,
database, reindex, environment or volume action occurred.

## What changed and why

Two raw follow-ups lack the explicit subject present in their preceding user
turns. Retrieval finds the gold pages, but the current-question-only source
judgment correctly requires clarification. The helper distinguishes actual
raw-only navigation clarity from a bounded literal subject in the most recent
preceding user turn. It never manufactures a name, reads assistant content as
an antecedent or scans older user turns after the latest turn is ambiguous.

The anchor is at most 160 characters/twelve words, an exact unique source span,
with character/UTF-8 offsets and exact question/subject hashes. Multiple topics,
unsafe controls, additional instructions, malformed history, event referents,
generic subjects and unsupported grammar remain clarification. The helper
imports only the standard library and performs no I/O or provider work.
An additional validator binds the latest-user selection to the complete
admission-bounded tuple; checking one question's bytes alone cannot establish
which database message preceded admission.

The initial helper could not parse the two preceding turns. A blinded reviewer
independently froze the exact expected offsets and hashes before reading helper
or source-selection outcomes. Only generic grammatical frames were supplied:
a passive subject with a purpose qualifier and a first-person reading-about
statement. Generic rules for those frames now match both independent spans;
no entity-specific keyword or lecture-derived rewrite was added.

## Checks and evidence

- `venv/Scripts/python.exe -m pytest tests/test_source_navigation_context_v1.py
  tests/test_navigation_query_candidate.py tests/test_source_navigation.py -q`
  from `backend`: **150 passed**, including **110 new** contracts.
- Actual metadata-only local probe preserves all twelve cases: ten remain
  raw-clear with no anchor; both unresolved follow-ups produce exact literal
  spans matching the independently frozen offsets and subject/question hashes.
  No question, subject, lecture or source text is recorded here.
- Independent expected-span metadata SHA:
  `f473d4e87d992d61b9f43573b28c67adef77ca401f522b9c72e683846d6b0ffe`.
- Aggregate metadata is retained in ignored `.agent/.verification/`, named
  with the helper's byte hash. It reports zero provider calls and DB queries.
- One attempted whole-file metadata print was rejected by automatic review
  before execution because content was not proven safe. The accepted safer
  inspection prints only whitelisted key/type/label metadata; no content was
  exposed. The diagnostic now prints only counts and aggregate hashes/paths.

## Integration requirement and limit

The existing worker `_bounded_history` reads the latest thread history at
execution, excluding only its current question ID. It can therefore include a
later queued user question. Future integration must snapshot the immediately
preceding user message under the enqueue/thread lock, with strict admission
ordering, ID and exact SHA, then recheck current owner/thread/Subject/revision
and message expiry before use. The helper cannot prove SQL ordering from strings.

Raw current-question embedding stays unchanged. Sending even the bounded
literal subject to a provider needs a separately versioned source contract and
fresh exact private-transfer envelope. These local parser/provenance results
do not prove source-selection quality, release readiness or Ask enablement.
