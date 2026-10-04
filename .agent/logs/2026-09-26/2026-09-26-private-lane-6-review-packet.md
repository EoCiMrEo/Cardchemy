# Lane 6 private review packet

## Scope and starting context

- The current Lane 6 representative private corpus item remains open. Six
  direct source/question/claim pairs were previously owner reviewed, but
  paraphrases, follow-ups and several negative/source-shape categories lacked
  independent owner labels. Existing lexical-only proxies and real direct-query
  ranks cannot stand in for those labels.
- The active local stack and populated Knowledge were preserved. No plan
  checkbox, Ask policy, model selection, `.env` or database data changed.

## Implementation and checks

- Added `scripts/build_private_lane6_review_packet.py` and keyless tests. The
  reader reuses the authorized owner/Subject, reviewed/published, current
  revision and active embedding-space scope. An exact eligible chunk quote is
  aligned with its canonical page before display. Private text appears only in
  an escaped static local HTML file; no raw content enters stdout, repository
  fixtures, logs or telemetry. Missing/unrun controls stay explicitly pending.
- The 20-row packet has six prior direct seeds, four paraphrases, two
  follow-ups, semantic negatives and explicit access/provider/generation
  placeholders. The output-root guard rejects an unwritable or absent host Temp
  bind mount before reading the database, and rechecks before writing. The
  one-shot Compose command uses the development profile, a read-only scripts
  mount and no dependency startup.
- Focused keyless tests passed **31**; an independent review found no blocker
  after the output-root guard. Context validation passed **37 required files,
  76 guides, 1,199 local links**. Direct preflight from root and backend read
  no database and made no provider request.
- One read-only local creation succeeded through the current answer-worker
  image. It wrote a neutral-named HTML under the host OS Temp directory:
  **20 rows, 12 source-bound, 8 unavailable/unrun; zero provider requests,
  zero database writes, zero new reviewed labels**. The first Compose invocation
  without the required development profile failed project validation before
  starting a container or reading the database; the guide command was fixed.
  All eight normal app services remained running afterward.

## Limit and cleanup

- The owner was asked to review only the six new source-bound cases by case ID
  against their original PDF pages. Acknowledging the request is not a label;
  the private corpus and quality gate remain open until explicit decisions are
  recorded. No private HTML path or excerpt is stored in this log.
- The owner subsequently reported **D01–D06 Yes, P01–P04 Yes and H01 Yes** for
  the exact source-bound excerpt/page cases. For **N01 No**, the owner clarified
  that the selected excerpt does not clearly refute the wrong candidate. Treat
  N01 as **insufficient negative evidence**, never as a confirmed contradiction
  or a passing safety control. The remaining eight packet rows were reported
  as unavailable/error; they are deliberately unexecuted placeholders and
  acquire no owner quality label. Thus the packet contributes eleven reviewed
  feasible cases, one rejected negative selector and no completed access,
  provider or sparse-source private controls.
- The packet is intentionally temporary. Keep it only until the owner records
  labels, then delete that exact task-created Temp directory; do not delete any
  other Temp content. Revalidate the published revision and embedding space
  before using labels for a later replay.

### Review-copy correction for future packets

- The owner described the eight deliberately unexecuted rows as errors. The
  packet builder now labels seven as planned separate controls and N02 as a
  corpus-wide unsupported case pending a separate evaluation. None presents a
  review radio button. The summary separates eight planned controls from an
  actual missing source in a source-bound case. N01 explicitly asks whether the
  selected excerpt itself refutes the wrong candidate and tells the reviewer
  to choose No if counter-evidence is absent. This changes future packet copy,
  not the already reviewed private HTML or its labels.
- Focused keyless packet tests passed **32**; preflight read no DB and made no
  provider call. Context validation passed 37 required files, 76 guides and
  1,202 local links. A separate negative-source packet remains under design;
  the eleven reviewed positives do not establish negative acceptance safety.
