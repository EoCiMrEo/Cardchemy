# AI Provider Enablement Fix

Date: 2026-09-15

## Problem

The Compose security boundary intentionally exposed `AI_API_KEY` only to the
generation worker. The API nevertheless used the presence of that credential
to decide whether PDF generation was available. As a result, the worker could
see the key while the API reported `generation_available=false`, and the
frontend disabled **Generate with AI**.

## Resolution

- Added `AI_PROVIDER_ENABLED`, a non-secret operator switch shared by the API
  and generation worker.
- Changed generation admission and the limits response to use that switch,
  without exposing provider credentials to the API or frontend.
- Preserved `ai_provider_configured` as the process-local connection-material
  check used by provider construction and diagnostics.
- Made the generation worker fail at startup when native Gemini is enabled but
  neither `AI_API_KEY` nor the legacy `GEMINI_API_KEY` is present.
- Made a disabled worker wait without claiming queued jobs, so the flag is also
  an effective cost-control kill switch.
- Added the switch to both environment examples and documented native Gemini
  setup (`AI_BASE_URL` remains empty).
- Enabled the switch in the ignored local `.env`; no credential value was
  copied into source, test output, or this log.

## Regression Coverage

- API admission succeeds from the non-secret enablement flag even though the
  API process has no provider credential.
- A key alone does not enable generation when the switch is false.
- Enabled Gemini rejects missing worker credentials at startup.
- The legacy Gemini key fallback and keyless local OpenAI-compatible endpoint
  remain supported.
- A disabled generation worker does not claim queued jobs.
- Live-provider tests use the explicit enablement flag and remain opt-in.

## Verification

- Targeted backend tests: `36 passed, 1 deselected`.
- Full local backend suite: `140 passed, 23 skipped, 1 deselected`.
- `docker compose config --quiet`: passed.
- Development Compose configuration: passed.
- Production Compose configuration with safe validation overrides: passed.
- Rebuilt and recreated `backend` and `worker`; both became healthy.
- Runtime inspection confirmed:
  - API: provider enabled, no provider credential.
  - Worker: provider enabled, provider credential present, Gemini adapter
    selected.
  - API readiness endpoint returned HTTP 200.
- Source diff whitespace check: passed.

No paid/live Gemini generation was submitted during verification. The provider
call remains an explicit operator/user action.
