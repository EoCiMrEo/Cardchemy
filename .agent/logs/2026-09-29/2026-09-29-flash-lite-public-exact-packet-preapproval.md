# Exact public Flash-Lite packet: zero-call preapproval

Date: 2026-09-29 (America/Chicago). Branch `main`, HEAD `6c02d6c`.
This is a credential-free, provider-free calibration preparation and
preapproval check for the **proposed** Gemini 3.5 Flash-Lite public pilot.
No plan/ADR amendment, provider call, private Knowledge transfer, DB write
or Ask activation occurred. Existing pilot claims and local data were preserved.

The pinned public blind packet SHA-256 was
`7ec9a83245fd432ff9f19047d1aa5aab1835a0bc9fdab04d9807d87787d19ae7`;
the independently frozen public labels SHA-256 was
`bab352ebd06bc77d2bbbfa49f7e960d946bcb5af4d2346f943412c1699cd8ad1`;
the freeze receipt SHA-256 was
`114e122636eb1f8b6d334e550ac4aa0009fd34925238b035fd4721abf330cc51`.
The new evaluator/caller SHA-256 values were respectively
`8efec637cf54f35c45003e0b3cdf8f534ca01bab766e5a2eab0f0d11909d4ac5`
and `31089ce26658610ff7d5c95246897538140e75ee7e7e0a89d4bd838ce62c1344`.
The runtime source-judgment and navigation module SHA-256 values were
`9de07e17fb54c54464d58912d96f53f520b9500ffef16b87c9deef78fe42a73f`
and `048b217cfc6db58502bbaee311f54f115d954aa4717caf00307442cbd3c2a3a6`.
No content or secret bytes are logged.

The new calibration preparation in OS Temp produced **48 callable**, zero
clarification groups, fingerprint
`a7d8efb4a1472612c2500e4254548d7c79ea48f9b9c75025737993d08c7ffe50`,
requests SHA-256
`70a3983993da01043b57272e3d7800ed2a964ea2a4000fa9495ab8ba21966763`
and prepare-receipt SHA-256
`6ce0540c4527a36ff2beed14a0bffd619972bed191b3b883e15fd7947a24eb0b`.
The exact `--preapproval-preflight` passed with maximum serialized REST body
7,627 bytes and conservative input-token admission estimate 8,139 under the
8,192 token cap; it read no key or approval and consumed no run/score claim.
The 43 focused offline tests passed independently. The dedicated
`RAG_SOURCE_JUDGE_API_KEY` remains **unset** by a secret-safe presence check;
the owner chose to create and enter a separate key in the same Free-tier
project. No permission to copy another key was inferred.

An exact endpoint/model/price/call/token/time/cost approval has been requested
as a separate next step. If approved and after the key is entered, a new
same-identity approval-aware zero-call preflight must pass before any live
request. The one-use approval and calibration claim then prevent replay;
heldout remains sealed pending a complete passing calibration. Ask remains
disabled and Lane 6 remains 3/7.
