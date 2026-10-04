# Public visual-page input preparation and development review

Date: 2026-10-01 (America/Chicago). Scope is the owner's
[approved offline preparation](2026-10-01-visual-page-source-input-approved.md).
Starting tree: dirty `main`, HEAD `6c02d6c`; existing edits and retained data
were preserved. Lane 6 remains **3/7** and Ask is not activated.

## Source-bound preparation completed

One successful preparation retained every original 66 question and 264 pair,
and rendered all 80 distinct cited physical pages from the same four pinned
public PDFs. No crop, semantic annotation, OCR replacement or selective
failure-only rendering was applied. Native text/cue offsets were checked
against the copied PDF bytes. Original PDFs were unchanged.

Output: `C:\Users\eocim\AppData\Local\Temp\cardchemy-visual-input-v1-vwcn8r3i`.
Freeze SHA: `1079eab34382f62467757209040e40113ee4bae76082ea98c4e644bd378e5bac`.

- Raster/payload assembly elapsed: **42,198 ms**, within the supervisor's
  complete 600-second deadline, which includes source preflight.
- Largest PNG: **818,519 bytes**; all 80 passed full-stream/CRC/dimension
  checks at <=1,600-pixel long side / 2 MP / 1 MiB. Total raster bytes:
  **14,915,965**.
- Largest payload: **3,392,757 bytes**; largest complete prospective wire,
  including system prompt/schema: **3,395,442 bytes**, below 6 MiB.
- Complete roster: 80 image files, 66 input files and 66 payload files.
  Each final wire also has its own SHA/byte binding in the manifest.
- `resource_limits_enforced=true`; `provider_calls=0`, `model_inferences=0`,
  `quality_pass=false`, `provider_trial_ready=false`.
- Owned PDF snapshots were removed after completion. Sources and immutable
  parent audit/review/failed-trial files were preserved.

## Independent review and repaired startup

Independent code review found and repaired external freeze anchoring,
complete artifact/receipt/roster checks, default mock refusal and source
reopen races. Four exclusive source snapshots are rehashed while held under
deny-write/delete locks through extraction and rendering.

Actual Windows synthetic checks proved four-CPU affinity, 2 GiB aggregate
job committed-memory limit, no resource-job breakaway, timeout handling and
worker/descendant termination. Invented file bytes proved read locks allow
reads and deny modification/deletion until release.

Two startup-only invocations stopped before source/image preparation. Their
original output directories remain unchanged:
`cardchemy-visual-input-v1-a5bmktl6` and
`cardchemy-visual-input-v1-cvgfdsjo` under Windows Temp.
The first cause was the Windows venv launcher's additional inner job:
a null job query inspected that job instead of the resource ancestor. The
repair uses a collision-checked unique job name, explicit membership and
limit queries, while retaining all enforced limits. The second cause was
an incorrect fixed prefix length in worker identity validation; generated
identities are now checked using the actual prefix length. Both repairs
were reproduced/verified through the actual supervisor and venv with a
synthetic no-file worker before the successful preparation.

The Windows behavior was checked against Microsoft's
[job query reference](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject)
and [job-object guide](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
No admission check or resource budget was relaxed.

## Frozen development review

The [prospective measurement contract](2026-10-01-visual-page-measurement-contract.md)
retains all tri-state parent labels, separates clarification from binary
no-match, and preregisters the deterministic 16 agreed-weak sample plus
five diagnosed gaps. It permits exactly one added four-page conclusive
control only after independent review; the original unresolved case stays.

Review root:
`C:\Users\eocim\AppData\Local\Temp\cardchemy-visual-feasibility-v1-7ut522w8`.
Packet SHA: `4f1d237852e8bd9894437fabfc060072ab49313fd5778a84fc637fb316aac1c8`.
Two fresh reviewer contexts received no old labels, gap/weak roles or model
choices. Both completed all 29 supplied image/question inspections at the
exact input resolution. Their sealed hashes are
`37f388ac626785c7f067323d65ee02ebbec3aa208304b12352b49857c18cbf6d`
and `8f03c7017f9843c9d1026b352b203c81c8feae169c4af92b052d11c8f87dcf06`.
The complete content-free summary SHA is
`e38be8cf9c0e0473cf02d5d0397b1e54fb9ba9963a8f5dc489e992a6128958e4`.

- Readability: **29/29 Yes from both**; input and cue agreement: **28/29**.
- Three of four diagnosed visual omissions are now represented by useful
  input according to both reviews. P146 remains **No/No**, requiring outside
  inference to connect the displayed structure to the requested condition.
  This is semantic coverage, not unreadable raster output.
- P072 is **Yes/Yes** under the concrete-learning-step rubric; this does not
  replace its original sealed labels or retrospectively change any score.
- Sixteen agreed-weak controls: A = 14 No / 1 Yes / 1 Unsure;
  B = 14 No / 2 Unsure. R11/P119 is Yes versus Unsure; R16/P009 is Unsure
  in both. These unresolved inputs are not converted to weak or useful gold.
- All four pages in the added control are unhelpful according to both,
  but the question's target record/event is not uniquely identified:
  clarity No versus Unsure. **The new control is not admitted.**
- The original uncertainty question stays separate. No original annotation,
  question, score or ledger was rewritten. No heldout was opened.

The approved stopping rule applies: `input_feasibility_passed=false`,
`provider_trial_ready=false`. A future trial cannot use this result as an
input feasibility pass, a model accuracy measurement or a release pass.
The source/condition and control-reference defects need a new bounded
decision before further experimentation; no new prompt sweep was run.

The read-only image tool denied Windows Temp PNG access. A separately bounded
no-render worker copied exactly the packet's 20 unique images, with SHA/byte
equality checked, into owned workspace scratch. The original packet and
image bytes stayed unchanged. Access mapping SHA:
`b437660b9344fb00c8d346112dbf9dc08ef2d8f089d78996fba7225e2136224c`.
Scratch is removed after reviewer completion; the content-free binding
receipt remains. This access workaround does not enhance image detail.

## Verification and limits

**217 related synthetic tests passed** in the normal backend runner, including
the 59 preceding annotation/summarization contracts and 158 visual-input,
wire and review contracts. These cover
complete input preservation, PNG corruption/bounds, source/image substitution,
freeze/receipt integrity, resource/worker admission, snapshot races, closed
ID/status parsing, no weak padding and agreed-weak sample selection. Tests
use invented bytes and make no provider call. Context check passed
37 required files / 79 guides / 1,709 links before this result record.
Final documentation/whitespace and owned scratch cleanup checks follow.

No frontend/application policy/schema changes, root environment inspection,
database/private Knowledge access, heldout opening, downloads, token-count
API or paid/model execution occurred. Earlier service/frontend checks are
not relabeled as new release proof. Rendering and input review are not model
accuracy, provider availability or permission to send private page images.
Existing >=90% usefulness, hit/cardinality/no-match, availability, access
and release gates remain open and unchanged.
