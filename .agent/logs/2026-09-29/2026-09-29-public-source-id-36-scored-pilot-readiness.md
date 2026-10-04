# Public Gemini 3.6 source-ID scored pilot readiness

Date: 2026-09-29 (America/Chicago). Branch `main` at `6c02d6c` with the
shared Lane 6 worktree preserved. This records a **keyless public-only
preflight**, not paid authorization, a model-quality result or Ask activation.
The retained local database remains at `20260928_0029`; Ask remains disabled.

## Frozen data and actual transfer scope

The pinned 96-group packet SHA-256 is
`7ec9a83245fd432ff9f19047d1aa5aab1835a0bc9fdab04d9807d87787d19ae7`.
The independently reviewed labels SHA-256 is
`bab352ebd06bc77d2bbbfa49f7e960d946bcb5af4d2346f943412c1699cd8ad1`;
their freeze receipt SHA-256 is
`114e122636eb1f8b6d334e550ac4aa0009fd34925238b035fd4721abf330cc51`.
An independent read-only audit verified the manifest and actual original-PDF
hashes, official course source, first-page CC BY 4.0 notice, all 384 candidate
physical pages and exact cues, all frozen label identities and 96 split/form
identities. The **whole pilot spans eight distinct public PDFs**: calibration
lectures 22/25/26/27 and heldout lectures 28/31/32/38. Each individual
four-page request contains pages from exactly two of those PDFs. No private
Knowledge, user identity, chat history or PDF bytes enter the model-facing
request; only the public current question, bounded page/cue text and ephemeral
candidate IDs do. The earlier two-call diagnostic used only its first slate;
that diagnostic approval did not cover this eight-PDF pilot.

## Dormant candidate and guard

`scripts/evaluate_source_id_multipdf_36.py` and
`scripts/run_public_source_id_multipdf_36.py` are separate from the consumed
Gemini 3.8 pilot ledgers. The evaluator freezes the same public labels and
gate before scoring. The runner rebuilds the request from the pinned packet,
rejects a pending authorization ID and requires a matching, separately approved
receipt before reading a credential. It probes output, approval and scoring
ledger permissions before egress, then uses exclusive approval/run/call/score
claims. A failed or uncertain physical request stops without retry. Calibration
has at most 48 calls; only a passing frozen calibration score permits the
48-call heldout. The heldout inherits the original pilot clock, prior known
cost and six-second cross-split spacing. Provider responses must pass exact
issued-ID, finish, size and usage validation. No score can activate Ask.

The proposed endpoint is
`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent`
with `gemini-3.6-flash`, low thinking, `store=false`, no redirect, no tool and
only an ordered array of zero to three issued source IDs. Maximums: 96
physical requests total; 8,192 input and 1,024 combined output/thinking
tokens per call; 786,432 input and 98,304 output tokens total; 30 seconds per
call; 90 minutes total; at least six seconds between call starts; zero retry.
The conservative admission prices are USD 1.50 input and USD 7.50 output per
million tokens, with a **USD 2.00 new-spend ceiling**. These are above the
[official September 2026 standard prices](https://ai.google.dev/gemini-api/docs/pricing)
and guard against later price changes; actual invoices and failed-call costs
may differ. Three prior Gemini 3.8 single-call failures have unknown actual
cost; the separate Gemini 3.6 two-call transport diagnostic had USD 0.004322
under the same conservative guard. The new pilot requires its own explicit
operator approval, not the diagnostic's consumed approval or a configured key.

## Provider-free checks and limits

The fresh calibration preparation yielded 48 callable groups, zero local
clarifications and a 7,219-byte maximum abstract request wire. Its
pre-approval fingerprint is
`61072e1a3ebd6d4a10a4232cfd10342b9bd75c4b0fb9e4ff977c399f916e8eec`;
requests SHA-256 is
`c06a2d30895f95fbeabed4f110bed1b80e28163c83f83f8f7e29abf7d2e3b40c`;
prepare receipt SHA-256 is
`411c12081157f9d6d26c55c2abe1a257c75c05800c064ad7bfd0b953bba73fcb`.
Changing the pending authorization ID changes the caller hash and invalidates
that prepared receipt, so preparation must be repeated **after** exact owner
approval and before any request. The subagent's combined fake-transport and
scorer run passed 58 keyless tests; a separate focused run passed 28/28.
The scorer ledger ACL probe passed under the current local identity. A paid
run and its scoring must use that same identity or repeat the probe under the
intended identity. No approval receipt was created and no provider request
was made in this readiness work.

The retained v4 worker is currently pinned to `gemini-3.8-flash`. Even a public
Gemini 3.6 pass is only candidate evidence: a model/policy change needs an
explicit approved plan/ADR update, implementation and independent private
original-PDF measurement. The public four-page, two-PDF slates cannot by
themselves establish the worker's larger candidate-pool behavior. The four
open Lane 6 quality/release checklist items remain open; Ask stays disabled.
