# Approved learned source ranking audit

Date: 2026-09-27. Scope: the operator approved the
[bounded audit recommendation](2026-09-27-learned-source-ranking-feasibility-recommendation.md)
after frozen v7 failed independent source-sufficiency measurements.

Preserve root `.env`, retained data/volumes and all existing source-only,
access, exact-offset, migration and release invariants. Ask remains off and
Lane 6 remains 3/7. No Gemini request, model training, retained DB write,
runtime activation or rollout is authorized by this audit. The existing
retained installation remains v5/schema `0023`; the latest diagnostic image
contains v7/schema `0025`.

Plan and ADR-022 record only the approved experiment. Independent public
question/window labels and split are frozen before model scoring. Public
artifact revision, file sizes/hashes, network attempts, resource limits,
calibration rule, heldout metrics, failures and cleanup will be recorded here
without private source text, prompts or raw responses. Score is a candidate
ranking signal, never assumed proof of source sufficiency.

## Approved public bundle acquisition

The one approved acquisition finished and its durable ledger reports
`verified`, **7 GETs** (including metadata and redirect), **154,481,848
received bytes**, no per-file retry, against the 10-GET/300-MiB/30-minute
guard. The full local five-file bundle is **154,478,394 bytes** and the
manifest SHA256 is
`0fd8b4b5d1131847f7e39247c0df40fcdb602509b60f4ae18f713b38e175cc08`.
The model INT8 graph is **150,871,837 bytes**, matching its published SHA256
`ecc6a0ae67cee3d898167802383112d9185ca9250e07bd5d1fa65019b050179d`.
The four small config/tokenizer files passed upstream Git-object hash checks
before their SHA256 hashes were frozen in the local manifest. The downloaded
bundle is ignored under `/artifacts/`; no public file was committed.

The downloader's 33 offline HTTP/ledger tests plus the audit harness's 16
offline tests passed together (**49/49**). Host-only independent bundle
verification matched the manifest and size. The subagent controlling the
download reached its usage limit after launch, but the durable ledger and
fully hash-verified files establish completion; the lost session was not
restarted. The one-shot ledger remains consumed. No model inference, provider
request, private lecture read or database mutation occurred during download.

A temporary answer-worker-derived audit container was created with Docker
network mode `none`, four CPU and a strict 2-GiB total memory cap, without
mounts or app credentials. Only the public bundle and audit script were copied
inside. It independently verified all five artifact hashes and the same
manifest digest before any fixture or model score was loaded. The retained
application containers, database and volumes were left untouched. The
temporary container will be removed after this audit or a stop condition.
The first idle container inherited an answer-worker DB healthcheck and became
`unhealthy` because network mode is `none`; it had not loaded a fixture or
model. It was removed and replaced with the same restricted temporary setup
and `--no-healthcheck` before any inference, so periodic readiness checks
cannot perturb the CPU/latency audit. The approved one-shot model scoring was
not consumed by this environment correction.

## Independent public case preparation

The author first froze 96 invented cases with 32 calibration and 64 heldout,
balanced by eight declared relations. A blind first-pass source reviewer
accepted 16/16 calibration sufficient, 16/16 calibration insufficient,
32/32 heldout sufficient and 30/32 heldout insufficient; two heldout controls
were Unsure. Many negative passages explicitly announced missing content and
were judged too easy. The author preserved those files/labels, then prepared
a second blinded revision with natural same-topic wrong-owner/condition and
partial-relation passages before any score was observed. Independent review of
the revised packet remains pending. Do not score, choose a threshold or reuse
the first-pass outcomes as a release measurement before the final labels and
fixture hash are frozen.

The second blind revision exposed two material heldout mechanism-label defects
before model scoring. That revision is preserved as an immutable review trail;
the author is preparing a corrected revision for another independent blind
check. No model score has been observed in the corpus-authoring loop.

The final fourth author revision corrected the mismatched questions; a fresh
blind review agreed with **96/96 labels**, with zero Unsure/malformed relations.
Prior drafts and first-pass labels were preserved. The final exact fixture
digest is `cec2c60b265125df65cc99b6d71a5bf1a59fe0f8da657ee746bbe36d2101aecf`;
its private source-review aggregate digest is
`c05ebb8152ec5a25f48923d196b2b177365b7a19a75c81dfbc828a5d03f62dc9`.
It contains 32 calibration and 64 heldout cases, 16 local prior-question
contexts, eight balanced relation families, 48 sufficient/48 insufficient
labels, and exact windows no longer than 180 characters. Synthetic near
negatives are more natural than the first draft, but some explicitly negate
alternatives; public success alone would still need private qualification.
No score or model code informed authoring/review. The frozen file was never
modified after scoring; its SHA256 matched again afterward.

Preflight found that the author's acronym-family label used a hyphen while
the audit harness expected an underscore. The **frozen fixture was not edited**.
The harness maps exactly that one alias to the canonical relation in memory,
with a new offline test; this was done before any model score. Final harness
digest: `47f99788518e00a8b8a1541c44bcff6aa65d91f4462b5c3fabeb0d5860b616e0`.
All **50/50** downloader/harness safety tests passed after this correction.
The offline container verified matching script, fixture and bundle hashes,
all 96 schema/split/window invariants and zero model inference in preflight.

## Single frozen public inference result and stop

One audit execution ran in the temporary Docker container with network
disabled, no app credentials and no retained DB mount. The calibration rule
used a strict threshold above every one of its sixteen insufficient raw
scores; the threshold was frozen to
`calibration-rule.json` (SHA256
`db01282dc864dae636a0a72cc60e91797af4cd3b61b646ebdac3b4e4c440e06b`)
before heldout scoring. It selected **4/16 calibration sufficient** and no
calibration insufficient source. On heldout, it selected **0/32 sufficient**
and **0/32 insufficient** windows. The pre-registered public gate required
at least 28/32 positive and at least 3/4 per relation, with zero false
primary. Status: `public_quality_rejected`, `candidate_passed=false`.

Technical resource guards passed: startup **1,716.813 ms**, 30-window p95
**2,773.142 ms**, peak added RSS **614.34 MiB**, complete input maximum
**70 tokens**, and total scoring **34,531.813 ms**. These numbers do not rescue
the quality failure. They show only that this pinned INT8 implementation is
feasible under the proposed CPU budget; they do not establish sufficiency of
another model or of real lecture results. The experiment made zero provider
calls and zero database writes. No private lecture regression, prospective
original-source audit, paid indexing or real-query retrieval was run after
the public failure. The retained Ask gate stays off and Lane 6 stays 3/7.

The ignored local aggregate artifacts are under
`artifacts/source-ranker-audit-20260927/results/`:
`audit-freeze.json` SHA256
`51224116fd8859ce9bd7dee06b7b393279044ee20e8ede3552cca32e87dc7b0f`,
`calibration-rule.json` SHA256 as above, and `audit-result.json` SHA256
`8cb2835322a920747207f4c20858a69f561b668027bfdb3facf6c7ebe6a295ab`.
They contain aggregate metrics and hashes, no source questions/windows. The
temporary audit container was removed; the hash-verified public bundle and
consumed download ledger remain ignored on disk for reproducibility. The
retained application services and volumes were not changed.

This is a failed **candidate audit**, not proof that all local learned
classifiers or all retrieval architectures fail. It reinforces the separation
between topic-relevance ranking and evidence-sufficiency classification.
Any new task-specific model, training corpus, score contract or alternative
learner-visible partial-source behavior requires another owner-approved
architecture/resource decision. No hidden rerun, threshold retuning or
private-case rescue follows.
