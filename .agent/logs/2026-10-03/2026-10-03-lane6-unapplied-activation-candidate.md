# Lane 6 unapplied activation candidate

## Scope and custody

The root requested an activation delta for review while the private continuation
trials are still using pinned source bytes. This work writes only an ignored
patch, its metadata, an ignored preparation script and this dated log. No
runtime source, tests, root configuration, database, image or service was
changed; no provider was called. The root retains ownership of application,
installation settings and release decisions after all trials and quality gates
are terminal.

Ignored candidate: `.agent/.verification/lane6-activation-candidate.patch`.
SHA-256: `7e4a16afd8e27e8b6b0d09fa2000ac788d14b675027a017419ee6c5a4c2006f6`.
The matching `.json` manifest records current byte hashes and proposed text
hashes for seven files. `git check-ignore` confirms all three preparation
artifacts are ignored. Seven current source/test byte hashes were checked
after preparation and remained identical to their manifest values.

## Exact proposed changes

| File | Proposed delta |
| --- | --- |
| `backend/app/config.py` | Change only `ASK_RUNTIME_POLICY_VERSION` to released `related_knowledge_navigation_v8` and its explanatory comments. The required release identity, historical read identities, budgets, role settings and default-off flags are unchanged. |
| `backend/tests/test_config.py` | Explicitly inject the retired closed fence into the price/retry validation and pre-activation PDF-key negative scenarios. Keep the subsequent positive v8/PDF-key requirement. Add false Ask/judge/effective/source-availability assertions to the existing bootstrap-template validation. |
| `backend/tests/test_runtime.py` | Model the closed-fence negative scenario explicitly. Keep the existing positive v8, independent role and flag-matrix assertions. |
| `backend/tests/test_source_visual_runtime_profile.py` | Explicitly inject the retired fence for inactive disclosure and historical-v4 metadata cases. Keep current-v8 availability, wrong-space, unauthorized-before-read, credential-isolation and default-budget assertions. |
| `backend/tests/test_visual_source_judgment_policy_migration.py` | Assert the released constant equals v8 and the required release identity. Keep distinct historical readable identities and persisted snapshot/constraint assertions. |
| `backend/tests/test_visual_source_completion_migration.py` | Change its single current-source constant assertion to equality. Keep all historical snapshots, schema/budget and trigger roundtrip assertions. Include this module in the focused activation command. |
| `backend/tests/test_rag_shutdown.py` | Replace implicit reliance on the old global fence and retired answer-role settings with five explicit current-path shutdown cases: Ask flag off, source-judge off, embedding off, embedding price zero, and retired global fence. Preserve history reads, mutation/retry refusal and no-claim assertions. The disabled worker scenario now closes the actual source-judge role. |

No coverage, quality, security, accessibility or token/time/cost threshold is
deleted or lowered. Shutdown tests continue to prove that independent indexing
remains available when only Ask/judge/pricing is closed; deliberately disabling
the embedding role also disables indexing. The profile's `ask_enabled` field is
the installation/release/Subject-space gate, whereas `ask_available` and
`source_judge_available` additionally require the current provider roles and
pricing. The proposed assertions preserve that distinction and retain
`answer_available=false`; retired answer/local settings do not gate the new
source-only path.

## Checks actually performed

All seven proposed Python texts parsed successfully with `ast.parse`.
`git apply --check .agent/.verification/lane6-activation-candidate.patch`
passed against the current working tree. The patch was **not applied** and no
candidate test was executed. These checks prove syntactic and patch-context
readiness, not a passing activation test suite or enabled runtime.

After the root applies an independently reviewed delta, the focused command
from `backend` is the existing activation runbook command plus the completion
migration module:

```powershell
venv/Scripts/python.exe -m pytest -q tests/test_config.py tests/test_runtime.py tests/test_source_visual_runtime_profile.py tests/test_rag_shutdown.py tests/test_rag_source_only.py tests/test_rag_source_only_negative_gate.py tests/test_rag_answers.py tests/test_source_judgment_visual_v5.py tests/test_source_visual_v5_provider.py tests/test_rag_question_context_v2.py tests/test_visual_source_judgment_policy_migration.py tests/test_visual_source_completion_migration.py
```

The prospective retained sequence, two non-secret installation flags, matching
image smoke/security, old-job preview, heads/drift, health/profile checks and
flag-only rollback remain in
[the activation runbook](2026-10-03-lane6-activation-readonly-runbook.md).
Preparation does not satisfy the still-open private displayed-source or
release gates, authorize a provider call, or mark Lane 6 complete.
