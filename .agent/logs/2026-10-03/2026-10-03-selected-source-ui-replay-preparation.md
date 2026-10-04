# Captured selected-source UI replay preparation

## Scope and evidence boundary

Prepare an owner-local, read-only loopback fixture to render **actual captured
valid source selections** through the exact packaged frontend. This addresses
the distinction between opening a page through the published catalog and opening
the same page from its selected Ask reference with the exact adjacent quote.

The fixture uses T01–T07 from the
[partial private trial](2026-10-03-private-v8-twelve-case-partial-stop.md) and
D01–D04 from the [partial seed trial](2026-10-03-private-seed14-partial-stop.md).
It does not rerun either provider, create retained Ask jobs, change source labels
or enable the actual Ask runtime. HTTP, authentication, job IDs and history are
**synthetic**. Live SQL/publication/revision/PDF guards remain separate evidence;
this replay cannot prove persisted Ask history, browser-to-retained-job execution
or authentication.

The preserved dirty checkout starts from `main` at
`6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57`. No source, root configuration,
database, volume, original PDF, prior trial/approval or failure was changed.

## Prepared inputs and implementation

The ignored `.agent/.verification/private_selected_ui_replay.py`:

- validates the exact existing packaged asset manifest and all **50 assets**;
  uses no `frontend/dist` substitute and modifies no asset bytes;
- verifies the consumed private/seed stage and terminal-summary hashes, input
  pins, actual successful UTF-8 request wires, selected-guard hashes and issued
  source/PDF/page identities;
- reconstructs **22 selected references over 11 valid cases** in the captured
  order, using the actual issued source quote and canonical page offsets;
- finds exactly **three original local PDFs** by their full-byte SHA, retaining
  them in RAM; total matching bytes are **1,132,938**;
- uses the current catalog titles separately confirmed by root: Week 3/42 pages,
  Week 4/32 pages, Week 2/33 pages. Title metadata is not used to select or relabel
  a reference;
- returns exact bounded PDF metadata/ranges and the corresponding captured
  quote/page text to the existing real Ask/PDF components;
- stores no question, lecture text, PDF bytes, model response, credential or
  human identity in a tracked file or the preflight metadata.

Only content-free preflight/runtime metadata is written to ignored verification
files. Input private text necessarily exists in fixture RAM and can be shown
in the authorized local browser; request logging is disabled.

## Bounds and closed routes

The server is fixed to **127.0.0.1:8899**, self-shuts down after **3,600 seconds**,
and permits at most **4,096 handled requests** with eight concurrent servicing
slots. It rejects a different Host header. CSP permits only same-origin script,
worker/network resources, and no route forwards to the real app or a provider.

It accepts only GET/HEAD, plus the synthetic local auth-refresh response needed
to mount the frontend. Ask admission/retry, delete and other mutations return
405; unknown source IDs/routes return 404. PDF reads require a single valid byte
range of at most 8 MiB. Asset requests are served from the pinned in-memory
manifest map, with JavaScript MIME for `.js`/`.mjs`; filesystem paths are never
selected from the incoming URL. Authentication/profile replies are expressly
fixture data, not actual grants. The actual root `.env` and credentials are not
read or mounted.

Server startup requires a root-reviewed exact code SHA argument. **Preparation
has not started a server or operated the browser.** Root owns the rendered-card,
exact-quote, initial-page, canvas/fallback, adjacent navigation and focus witness.

## Deterministic checks and bound artifacts

The offline route checks passed for all **22 references**: exact quote offsets,
matching PDF SHA/metadata and valid ranges; oversized/multiple ranges rejected;
unknown IDs/routes, traversal and Ask retry mutations rejected. These pure
checks started no HTTP server and made **zero** provider/database/configuration/
credential/browser operations.

Two early preflight attempts exposed local schema/serialization mistakes:
the wire does not carry an extra cue-hash field, and its UTF-8 canonical
serialization differs from ASCII escaping. They refused before writing a
preflight or starting any server. Validation now compares the canonical source
hash and actual captured UTF-8 wire. No outcome or prior trial file was changed.

| Artifact | SHA-256 |
| --- | --- |
| Exact packaged frontend image | `e672a910c14e69f68fcecd974fac4435c258c0d12fcdbefca2b46889767ef694` |
| Unchanged asset manifest | `76e0c6c6efa99649ae9396ff58afcb4240dbb79eeb02b96bd2cb71d0c9dc82a2` |
| Reviewed prospective replay code | `3c20f78b09e230a2cff0d1b8283f1f1a76b91f1aa5f38344e72cedfef75580fd` |
| Ignored offline preflight | `785d15f9dcfc24a6eec9c8b037a8f8b974605b89f8a6035beb87f7cbaed77f51` |

This preparation proves neither a rendered browser observation nor a complete
private/seed/release gate. No Lane 6 checkbox is closed by it alone.
