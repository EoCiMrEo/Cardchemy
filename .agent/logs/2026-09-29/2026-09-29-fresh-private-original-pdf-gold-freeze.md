# Fresh private original-PDF gold freeze for Lane 6

Date: 2026-09-29. Branch `main` at `6c02d6c`. The current local application
has three published, original-PDF-backed Knowledge documents, schema head
`20260928_0029`, and Ask admission disabled. The owner requested independent
self-evaluation rather than another manual review packet. No paid provider
request, answer generation, source judgment, indexing or database write occurred.

## Discovery and correction

The existing `build_private_source_holdout.py` produced twelve cases, but they
are the historical T01–T12 question/page proposals the owner already reviewed.
Visual inspection reproduced the known problem: several pages mention a topic
without helping answer that question. Those cases are **not** a fresh holdout.
The temporary packet and its rendered page images were removed after resolving
their absolute paths under the OS Temp root. No previous private packet was
deleted.

## New frozen source gold

Authored a new 12-case Temp-only packet with four direct, four paraphrase and
four context-resolvable follow-up questions. Each selected original PDF page
was inspected through the current authenticated in-app page viewer **before**
any v4 candidate selection for these questions. The reviewer is the agent,
independent of runtime selection but **not** an external human reviewer. The
question wording and source content stay in the owner-private OS Temp packet,
not in this log or tracked fixtures. The output has no generated answer.

The generic `scripts/freeze_private_source_gold_v4.py` checks exact Temp input
SHA, form balance, distinct pages, review status and no prior candidate view;
then reads the authorized, published corpus in read-only transactions, binds
current document/content/index revisions, canonical page SHA and attached
original-PDF SHA, and rechecks the corpus snapshot before writing a Temp-only
stage-1 roster. Its default preflight performs no database/provider call.
Eight keyless boundary tests passed, including duplicate-question rejection.
The first freeze produced a correct packet
but exposed a Windows async connection-cleanup warning because the event loop
was closed before the pool; that superseded packet was removed. The cleanup was
fixed, tests were rerun, and the final freeze exited cleanly.

Final private packet directory: `cardchemy-v4-private-gold-hfl0gqzb` under OS
Temp. Its exact `stage1-gold.json` SHA-256 is
`53f0947bc3f01c488e28edb3f941bf13e51f8c85fdf7d3e8c8788ca976ab2477`.
The authored input SHA-256 is
`568c516476d8da1dd0a2f11dab0ad077397c7bd4cb39093e165eda78e9f227db`.
All twelve case/page pointers are distinct. Programmatic comparison against
the five exposed seed pages, all historical T pages and prior authored X
candidate rosters found **zero page overlap**. For each of the three document
slots, all four cases' archived original-PDF SHA values match the exact
corresponding local lecture file. The freeze reported zero provider requests
and zero database writes.

This packet establishes independently selected **gold pages** only. It does
not show that v4 candidate retrieval includes them, that any selected cue is
useful, that the public source-ID pilot passes, or that ≥90% of displayed
cards are useful. Candidate slates, exact-cue/page labels, a signed
post-candidate freeze, actual provider selections and release checks remain
open. Ask stays disabled. The populated volume, root `.env`, encrypted PDFs
and backups were preserved.
