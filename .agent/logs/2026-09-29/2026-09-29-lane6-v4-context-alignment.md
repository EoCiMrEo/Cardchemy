# Lane 6 v4 context alignment

Date: 2026-09-29 (America/Chicago). Scope: documentation only. The broad
pre-existing working tree was preserved. No application setting, database,
volume, original PDF, private Knowledge or provider request changed in this
subtask.

## Starting evidence and decision

The retained cutover record and current development state report schema head
`20260928_0029`, matching healthy application services and a closed Ask
release fence. [ADR-024](../../../docs/decisions/ADR-024-gemini-source-id-judge.md)
accepts a prospective ID-only source judge after one current-question
embedding, with zero answer generation. The source and configuration pin that
dormant v4 judge to `gemini-3.8-flash`. The separately approved public Gemini
3.6 transport diagnostic proved two valid responses but produced no quality
score and did not change the runtime model. Lane 6 remains 3/7.

## Corrections

- `PROJECT-MAP.md`, `docs/CONFIGURATION.md` and `docs/ASK_AI_SHUTDOWN.md`
  now identify the retained local schema as verified at `0029` with Ask
  disabled; they no longer refer to the earlier `0028` cutover snapshot.
- `docs/AI_PROVIDERS.md` distinguishes dormant v4 source-ID judging from
  retired answer generation. It describes one query embedding, at most one
  bounded judge request and no automatic Ask provider retry, and links
  ADR-024. Its model description remains the actual `gemini-3.8-flash`
  runtime pin, not the unscored public 3.6 diagnostic.
- `docs/architecture/SYSTEM-OVERVIEW.md` includes the prospective source-ID
  stage and the verified retained `0029` state while preserving the default-off
  and source-only boundaries.

## Checks and limits

`python scripts/check_context.py` passed after the log/index edit: 37 required
files, 79 active guides and 1,500 local links. `git diff --check` passed for
the changed tracked documents; it reported only line-ending conversion
warnings. This documentation correction does not score
public or private page usefulness, verify another installation, authorize
private-source transfer, activate Ask or close any Lane 6 checklist item.
