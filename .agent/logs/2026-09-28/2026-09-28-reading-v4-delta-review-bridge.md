# Public reading-usefulness delta-review bridge

## Scope and preservation

The v4 public audit's first independent review exposed useful-label imbalance,
third-party figure risk and cross-split semantic overlap before model scoring.
Two author-only replacement drafts and separately blinded full packets were
already held in OS Temp. This work prepared a provenance-preserving bridge so
unchanged question/source windows can retain their two earlier independent
judgments while changed windows receive new blinded review. The original
drafts, reviews and adjudications were preserved. No private Knowledge or
retained database was read.

## Implementation and checks

[bridge_reading_usefulness_reviews.py](../../../scripts/bridge_reading_usefulness_reviews.py)
pins every OS-Temp input by SHA-256, checks exact question/context/template,
source document, candidate text and page offsets before carrying a judgment,
and emits a separate delta packet and mapping. It rejects extra fields in the
blind packet and mapping, globally duplicate candidate IDs and altered source
identity. This prevents author labels or forged source fields from entering a
review packet. Its merge requires two complete independent delta reviews and
adjudication for every disagreement or uncertainty; it does not create labels
or run a model.

The pinned train delta has 28 changed candidates in 28 groups and 356 exact
carry-forward candidates. The evaluation delta has 27 changed candidates in
12 groups and 357 exact carry-forward candidates. The two packets have SHA-256
`a090c8d29dc6b29f458e2eddcab818c5704c66848becc97d781bbb7c6210b21c`
and `2f293c6497d54af4f6ef546ecdf16bfe7eaf1489df22ce1a8dc9d609977dc254`
respectively. They remain blinded; no author labels are present.

`backend/venv/Scripts/python.exe -m pytest -q
tests/test_reading_usefulness_review_bridge.py
tests/test_reading_usefulness_blind_review.py` passed **10 tests**. Synthetic
cases covered project/merge provenance, changed offsets, registered question
rewrites, forged pages, injected labels and duplicate IDs. The tests did not
merge the real packets or score the public model. Two fresh independent
reviews of the changed public PDF pages are still required, followed by
adjudication, admission and the separately approved one-shot offline audit.
Ask remains disabled; no provider, indexing or database write occurred.

After the stricter bridge validation was in place, a read-only derivation from
both pinned repair configs reproduced the registered delta-packet SHA-256
values exactly: 28 changed train candidates and 27 changed evaluation
candidates. No new packet or judgment was written.
