# Frozen published-roster query-vector packet builder

Date: 2026-09-28. Scope: bounded provider-only input for the separate
read-only source-navigation diagnostic. No provider call, application database
read/write, Ask admission change, Knowledge change, plan or ADR edit was made.

## Starting context and decision

The retained checkout had substantial unrelated, uncommitted Lane 6 work.
`main` was at `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`; that work was
preserved. The existing diagnostic consumes an exact private packet with a
roster SHA, active embedding-space hash, model and eleven case/question-bound
normalized vectors. The published-source page-only roster was already frozen
at SHA-256 `fca9588c20997424e716a726beac7a64db7bdde1036b18734db28ca4c8cdd730`.
No private question, PDF text, owner identifier or credential was copied into
the repository or this record.

The operator requested a guarded producer for that packet and deferred any
physical provider execution to a fresh, explicit one-shot approval. The
producer reads the frozen private roster and supplied scope identity only;
it does not connect to PostgreSQL. It uses validated Settings to compare the
configured Embedding 001/1536/`QUESTION_ANSWERING` space with the supplied
scope before constructing a provider. It uses native Gemini with SDK retries
disabled and application retries set to zero. The fixed envelope is eleven
serial current-question-only requests at most, 512 aggregate locally estimated
input tokens, 30 seconds per physical request, six minutes total, and a
USD 0.001 local cost bound at a conservative USD 0.20 per million input tokens.
The admission price is an estimate, not a current tariff or billing receipt.

## Files and boundaries

- `backend/scripts/build_private_query_vectors.py` adds static default and
  input-check preflights, matching fresh UUID4 flag/environment approval, an
  exclusive approval-used receipt, exact packet validation and exclusive
  private output. No result is written after a partial provider sequence.
- `backend/tests/test_private_query_vector_builder.py` supplies only synthetic
  questions, IDs and credentials; an HTTP mock checks the actual native SDK
  request payload, one question per call, no retry after a 429, private packet
  compatibility and fixed aggregate reports.
- `backend/MOC.md`, `PROJECT-MAP.md` and `docs/RAG_EVALUATION.md` point to the
  operator tool and state its read-only, paid-call and evidence boundaries.

On Windows Docker Desktop, a host Temp bind can expose permissive Linux mode
bits even if host ACLs protect it. The builder therefore requires a
container-local `/private` directory mode `0700` and roster file mode `0600`
instead of weakening the permission check for that bind. The intended one-off
container can receive only a read-only Temp roster copy and the required
embedding credential/profile, without an application DB network. Copying the
packet back to owner-private Temp is a separate operator step after completion.

## Verification and limits

- `backend\venv\Scripts\python.exe -m pytest -q
  tests/test_private_query_vector_builder.py
  tests/test_private_source_navigation_diagnostic.py` from `backend`:
  **40 passed**, keyless, no live provider or database.
- `python scripts/check_context.py` validated 37 required files, 78 active
  guides and 1,367 local links. Python compileall passed for the builder.
- The default CLI and missing-approval CLI tests returned fixed JSON with zero
  provider/database activity. The input preflight test checked the active
  injected Settings profile and roster without constructing a client.
- The native SDK mock sent eleven one-question `QUESTION_ANSWERING` requests;
  the resulting packet passed the existing consumer's SHA/shape/norm loader.
  A mocked 429 on request three stopped with three total physical attempts,
  no retry or output file, and unknown prior-attempt cost.
- Initial sandboxed Docker access was denied. A bounded approved escalation
  verified an isolated one-off `cardchemy-backend:0.1.0` container with
  `--network none`: `/private` was mode `0700`, and the default CLI returned
  `preflight_unexecuted`, zero provider requests and zero database reads/writes.
  The workspace E-drive read-only bind failed with Docker Desktop's `no such
  device`, so the two public diagnostic scripts were copied into the stopped
  container before it started. A stopped-container `docker cp` back to a
  temporary workspace file matched its source SHA-256, and that temporary
  copy and the one-off container were removed. This proves the no-call path
  and private-directory mechanics, not the active-roster/profile input
  preflight or a paid attempt.
- No actual root `.env` values, private roster bytes, live token usage, actual
  provider billing, hybrid retrieval quality or release gates were inspected
  or established. The operator subsequently approved the bounded eleven-call
  envelope; actual `--execute` remains a separate step outside this record.
