# Completed public source-usefulness contract audit

Date: 2026-10-01 (America/Chicago). The owner approved the
[all-case offline audit](2026-10-01-source-contract-audit-approved.md).
This record supersedes the partial progress snapshot, not the old pilot
results or gold. It reports annotation and input defects, **not Ask accuracy**.
Lane 6 remains **3/7** and Ask remains disabled.

## Completed procedure and preservation

All **66 questions / 264 candidate pairs** are retained. Each of three
22-question batches received two independent Codex reviewer contexts.
Every reviewer sealed all 88 wire-only judgments before receiving original
PDF identities. Each then reviewed every cited rendered page: 53 distinct
pages for batch 1 and 55 each for batches 2 and 3, across the four hash-verified
public calibration PDFs. Six complete wire and six complete page review files
are sealed. Three interrupted page stages completed in fresh contexts using
their own PDF packets without reading or changing the earlier wire labels;
this interruption/resumption is part of the provenance.

A seventh fresh reviewer saw the 16 disputed candidate inputs without
old gold, other votes, intended cardinality or model choices. That reviewer
sealed wire judgments first, then visually inspected all 16 distinct cited
original pages and sealed page/cue judgments. Three uncertain judgments
remain uncertain. These are independent agent assessments, not a new human
gold review. Contact-sheet inspection and original-detail checks are recorded
in the local coverage receipts; renders alone were not counted as inspection.

The combiner verifies original packet/review seals, the exact disputed
question/cue subset, source mapping, rubric and parent freeze. It does not
read historical gold until every fresh annotation, including adjudication,
is immutable. The final mapping contains all 264 old/new label pairs.
Historical provider responses were neither loaded nor rescored. No Gemini
request, application-model inference, download, private Knowledge read,
heldout opening, database/environment change or Ask activation occurred.
The populated volume, root `.env`, original private PDFs and backups were
not touched.

## Independent agreement and final annotations

| Dimension | Two-reviewer agreement | Final Yes / No / Unsure |
| --- | ---: | ---: |
| Actual bounded-input sufficiency | 255/264 (96.6%) | 106 / 158 / 0 |
| Original-page educational usefulness | 250/264 (94.7%) | 109 / 152 / 3 |
| Exact cue directs to useful material | 250/264 (94.7%) | 109 / 152 / 3 |

The 16 disputed pairs contained 37 disputed/uncertain fields. Final labels
change only those fields; original consensus is preserved. Relative to the
old joint page-and-cue label, **104 Yes and 147 No are unchanged**, **5 Yes
become No**, **5 No become Yes**, and **3 No become Unsure** under the
new independent assessment. All old annotations remain unchanged.

The adjudicated source counts are 11 conclusive zero-useful groups,
17 one-useful, 21 two-useful, 14 three-useful, 2 four-useful and **1 unresolved
group**. Thus the old binary corpus admission shape is not preserved.
Do not substitute these labels into the old scorer or open heldout as if
calibration had passed.

## Diagnosed input and measurement limits

Five of the 109 jointly useful page/cue pairs are **not sufficiently
represented in the exact input the source judge receives**. A further
read-only diagnosis verified exact packet equality and visually inspected
all five original pages: **four lack a visual learning relation** in native
text, **zero omit additional native text**, and **one has uncertain causal
attribution** because its figure adds a starting relation while the requested
transition is absent on that page. All five complete native page texts already
appear in their supplied contexts after extraction normalization. Expanding
native text from those same pages supplies no additional material. The
diagnostic did not change any sealed label; its one uncertain attribution is
distinct from the three unresolved final source judgments. Two other pairs
have sufficient-looking wire
text but an unhelpful original page. Wire sufficiency is therefore a separate
annotation, not proof of original-page utility.

All 54 conclusive positive questions still have at least one jointly useful
pair whose input is sufficient (18/18 in each direct/paraphrase/follow-up
form). This is an **idealized observable-input count**, not measured model
recall. For exact useful-set selection, input alone leaves an optimistic
maximum of 17/17 one-useful, 18/21 two-useful, 12/14 three-useful and 2/2
overflow groups. The two- and three-useful bounds equal their ceil(5N/6)
requirements: representational omissions already consume those entire miss
allowances before any model decision error. This does not prove another
text-only selector can attain the bounds.

Three page/cue uncertainties belong to one question whose application/system
referent is not settled by the supplied input. No label was forced to No
to manufacture the twelfth no-match case. The terminal report therefore
sets `prospective_feasibility.status=unresolved_labels`,
`old_corpus_shape_preserved=false`, `provider_trial_ready=false` and
`quality_pass=false`. The audit identifies rubric/gold and representation
defects; it does not exonerate or condemn the model on complete quality.

## Evidence and verification

Local text-bearing evidence remains in
`C:\Users\eocim\AppData\Local\Temp\cardchemy-source-contract-v1-dk54c0v7`.
Tracked evidence contains only counts, safe categories and hashes.

- Parent freeze SHA-256:
  `0d52a52bdc160f5cc159f5f2571b3c8562a7142d1493d027e00c5168f356ae28`.
- Old exposed label SHA-256 remains
  `401359c12875521238d50d8723f6261daf31474f245dde573250ad80de34c6a5`.
- Final aggregate report SHA-256:
  `59c3b1975e8032580f613d28966d15927f112d4ba5ec1d44e398c2e0bf515220`.
- Complete 264-pair mapping SHA-256:
  `1a25153b1ac6163671b1f18e69c836e3007faf44a2ba24875990e83e0938847d`.
- Five-page visual/input diagnostic receipt SHA-256:
  `c4fe6378fb0eb38ba8bd1ae4eb6a845572289da56fe822902f6c4ec21e7b4c24`.
  Its Temp-only sibling directory is `input-gap-diagnostic-4c68b080125741d887e7ac4b10af7878`.
- **59 synthetic tests passed**, including exact source-lineage binding,
  complete-roster preservation, tri-state disputes, immutable seal order,
  substituted-input/tamper rejection, and refusal to read old gold before
  fresh adjudication is sealed. A separate code-review agent independently
  reran all 59 and found no remaining blocker in the two helpers/test files.
- Context validation passed 37 required files, 79 active guides and 1,698
  local links before this final record; final documentation checks follow.
  Whitespace validation passed. No frontend/runtime source changed in this
  audit, so old frontend/service passes are not presented as a new release.

## Consequence

The approved offline audit is complete. A successor needs an explicitly
aligned source-navigation contract, a decision for unresolved controls and
input omissions, and compatible independent heldout annotation before a new
trial. Preserve all failed pilot receipts and their uncertain charges. Keep
the 90% displayed-usefulness, hit, no-match, access and release gates. Any
material plan/policy/input change or new provider execution still requires
the owner's applicable approval; this result authorizes none automatically.
