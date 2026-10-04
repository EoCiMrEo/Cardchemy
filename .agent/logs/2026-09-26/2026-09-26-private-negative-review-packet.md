# Lane 6 private negative review packet

## Scope and starting evidence

The first private review packet produced eleven owner-reviewed source-positive
cases. Its N01 wrong-acronym candidate received a No: the selected excerpt did
not clearly refute the alternate expansion. That is insufficient negative
evidence, not a passing contradiction control. The current Ask quality gate is
still open. Existing synthetic provider, malformed-output and access controls
do not supply independently reviewed private semantic negatives.

## Change

- Added a separate optional, provider-free negative packet builder under
  `scripts/`. It reuses the current owner/Subject, published/reviewed Knowledge,
  active revision/embedding-space and canonical-page alignment checks from the
  first packet, plus the guarded OS Temp-only HTML writer. It does not alter
  Ask runtime policy, the plan, database or original review packet.
- Two authored reversal cases ask whether an exact excerpt explicitly refutes
  the claim. An unrelated-question case asks separately whether the excerpt
  supports a true statement and whether that statement answers the question.
  A source missing or misaligned with its canonical page receives no owner
  radio control. The original N01 is excluded. No case is prelabelled as a
  successful negative.
- The default CLI performs no private read. Optional `--create` is read-only,
  makes no provider request or database write, and prints only a neutral Temp
  path, fixed counts and safe status. Private excerpts can appear only inside
  the escaped, script-free local HTML, never stdout, repository fixtures, logs
  or telemetry. The operator procedure is in `docs/RAG_EVALUATION.md`.

## Verification and limits

- `backend` targeted packet tests: **17 passed** for the original and separate
  negative builders, including source mismatch refusal, HTML escaping, no
  automatic quality labels, default keyless preflight, output-root guard and
  database close on scope change.
- Local default invocation returned `preflight_ready` with zero database reads,
  provider requests and writes. The database-backed create mode was **not run**;
  no private source was read and no new owner review was requested in this pass.
- Context validation passed **37 required files, 76 active guides and 1,206
  local links** after updating the project map and RAG evaluation guide.
- The new cases remain authored hypotheses until the owner sees the current
  exact source excerpts and original PDF pages, reports explicit decisions and
  the same published revision/embedding space is revalidated for any replay.
  A failed selection, a No or Unsure refutation, or an unrelated claim lacking
  either of its two separate labels cannot be counted as a safe negative.

## Subsequent guarded local creation

- After the keyless checks, the root agent ran the documented development
  Compose one-off reader against the current local published Knowledge. The
  task-owned HTML was written under host OS Temp, with **3/3 source-bound
  cases**, zero missing sources, zero provider calls, zero DB writes and zero
  new reviewed labels. The output path and private text are not recorded here.
- The HTML was offered to the owner for review by case ID. N11/N12 need
  explicit refutation labels; U01 needs independent source-support and
  question-relevance labels. No negative quality result is counted yet.

## Owner labels and interpretation

- The owner reported **N11 No, N12 Yes, U01 source Yes / relevance No** after
  reviewing the current local packet. N11 is another insufficient-refutation
  selection and must not be counted as a contradiction. N12 is one
  owner-confirmed explicit contradiction for its exact selected excerpt;
  U01 is one owner-confirmed source-supported but question-irrelevant pair.
- These are labels for the selected current source excerpts, not a runtime
  verifier pass, model-output replay or general retrieval-quality result.
  Recheck publication, revision and embedding-space identity before any later
  private replay. No content, titles, identifiers or private excerpt was added
  to this record.
- After recording those decisions, the root agent verified both task-created
  packet directories resolved inside the host OS Temp directory and each held
  only `review.html`, then removed exactly those two directories. The retained
  private Knowledge/database and unrelated Temp contents were untouched.
