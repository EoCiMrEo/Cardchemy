# Lane 6 one-shot query embedding and current hybrid diagnostic

## Scope and approved envelope

The operator explicitly approved one current-question-only query-embedding
measurement on the previously reviewed eleven-question published-Subject
regression roster. The endpoint was Google Gemini
`gemini-embedding-001:embedContent`, model `gemini-embedding-001`, task
`QUESTION_ANSWERING`: at most 11 requests, zero retries, 512 estimated input
tokens total, 30 seconds per call and six minutes overall. The conservative
admission price was USD 0.20 per million input tokens, with a USD 0.001 cap.
That price was a local guard, not a provider bill. No lecture text, chat
history, answer prompt, or database row was sent or written by the packet
builder. Ask admission stayed disabled.

The executed isolated worker made 11 embedding requests and zero retries in
121.606 seconds. The local estimate was 201 input tokens and USD 0.0000402;
no provider billing receipt was available. The private vector packet SHA-256
was `7633a5a48c28386ec99fe72f24736f72a4b204413956fc2bb8ac1443f3e9ae47`.
Its consumed one-shot receipt and vector packet remain in operating-system
Temp, not in the repository. After copying and checking the packet hash, the
isolated one-off container was removed. This approval is spent; no repeat
request is implied.

## Read-only current retrieval and independent PDF review

The already tested `diagnose_source_navigation.py` ran once with that frozen
packet against current published Knowledge using the actual v3/v9 hybrid SQL,
local follow-up query construction, neighbor/page loaders, and exact-window
selector. The one-off API image had no AI credential. Each case used a
repeatable-read, read-only transaction; provider and database writes were
zero. The roster SHA-256 was
`fca9588c20997424e716a726beac7a64db7bdde1036b18734db28ca4c8cdd730`;
the private observation SHA-256 was
`eabecc3a82c4e7fefbcf84467d5c2ca45cb933e65cd12649f6249a9e5896e6fd`.
The selector/retriever runtime hash matched the checkout. No question, quote,
source identity or vector was printed or stored in this log.

All eleven designated gold pages were current, indexed and present among SQL
candidates. SQL gold ranks were five at 1, two at 2, three at 3 and one at 9:
gold-page recall@5 was 10/11 and MRR about 0.646. Ten designated pages reached
the displayed top three; an independent original-PDF review found another
useful displayed page for the remaining case. That review separately graded
all 33 selected page/excerpt pairs: useful-page and useful-excerpt hit@3 were
11/11; useful top-one was 9/11; **strictly useful displayed cards were only
19/33**. All 33 exact excerpts matched their original physical PDF pages and
all 33 current PDF manifests were present. See the independent
[review record](2026-09-28-hybrid-original-pdf-independent-grading.md) and
private SHA-bound labels in Temp. The earlier lexical fallback on the same
exposed roster measured useful top-one 6/11 and strict useful cards 17/33.

These data separate retrieval from selection: the current hybrid candidate
pool finds the useful page on all exposed cases, but fourteen displayed
references do not help with the requested relation or condition. Hybrid
ordering improves top-one on this development set without solving display
cardinality. The roster has only one follow-up, is exposed, and is not a
fresh source/document-separated holdout. No authenticated browser PDF range
was opened in this diagnostic, no `no_match`/access gate was measured here,
and actual provider billing is unknown. The failed public GTE listwise
candidate was neither rerun nor integrated. Ask remains disabled.

## Preservation and next gate

The populated `0028` database, root `.env`, three encrypted originals,
backup, and matching application services were preserved. After a transient
unhealthy snapshot, the API and index-worker healthchecks were re-read and
had recovered to `healthy` without restart or mutation. The API still
reported `rag_ask_enabled=false`. All seven
local lecture PDFs have now been exposed in earlier development or holdout
probes, so a genuinely fresh document-separated evaluation cannot be made
from the remaining local files. New independently sourced material, a
pre-frozen question/page rubric, separate indexing/query authorization, and
actual published-source/browser measurements are still required before the
ADR-023 gate can pass. No plan checkbox or Ask policy was changed.
