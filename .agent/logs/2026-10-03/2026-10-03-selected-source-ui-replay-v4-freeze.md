# Complete captured source UI replay v4 freeze

## Scope

Prepared a separate ignored v4 helper, leaving the currently running v3 file,
its preflight and all historical artifacts unchanged. V4 retains all sixteen
previous cases and 34 actual references, then adds the ten completed seed
continuation outcomes: eight cases with fifteen additional references and two
empty restricted-source controls. The complete replay has **26 cases and 49
actual references**; no selected card, including weak private cards, is filtered.

All input, result, parent-checkpoint, packaged-asset and original-PDF hashes were
validated before use. Pure preflight passed **49** reference/quote/page/PDF/range
contracts and **two** empty `no_match` contracts. Unsupported mutation, missing
reference and unknown/path traversal routes fail closed. No live HTTP server was
started by this preparation; no provider, environment, credentials, database or
browser was accessed.

## Frozen bounds and identity

- Helper: `.agent/.verification/private_selected_ui_replay_v4.py`, SHA
  `8f3310c1c6e165a38aa4fec7ef0ce77976add391a6e7f93e532d3a1e3a01431e`.
- Preflight: `selected-ui-replay-preflight-v4.json`, SHA
  `5ef53d702848e7b0e5e28534816abfd7e452b30da25e9f5985ffdbc37e7da407`.
- Retains pinned v3 helper `be8aaf31…3c237360` and preflight
  `d0ef6378…88331c3`; new seed continuation stage `9cb5fe8e…17a5a91`,
  summary `34aee5fd…11fb60`, host receipt `eed8964d…5ed6d3`.
- On root authorization only: bind `127.0.0.1:8899`, at most 3,600 seconds,
  4,096 requests and eight concurrent handlers, self-only CSP and no proxy.
- The root owns stopping v3, reviewing the new code hash, authorizing/starting
  v4 and collecting browser observations. V4 writes distinct running/stopped
  metadata receipts and will shut itself down at the stated bound.

HTTP authentication, history and job IDs remain synthetic. Browser replay can
prove actual component/quote/original-page rendering of captured selections;
real access guards remain separate. The two empty controls test their restricted
candidate slate, not corpus-wide absence. No release or activation claim is made
until the independent browser observations and remaining gates are reconciled.
