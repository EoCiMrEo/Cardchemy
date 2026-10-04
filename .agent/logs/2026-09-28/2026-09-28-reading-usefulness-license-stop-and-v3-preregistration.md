# Public reading corpus: license guard stop and third preregistration

Date: 2026-09-28. The operator approved one corrected corpus-acquisition
attempt after the official schedule lacked the original lecture 13 and 23
links. This attempt used the preregistration SHA-256
`bef54089a3ef0ccd332c8dc8a07852c352e012bcb301b04ca9c72b742d8c48fb`
and a new OS-Temp directory. It made six GETs, received 13,049,543 bytes and
stopped at `pdf_missing_first_page_cc_by_4_license`. Four previously validated
PDFs (lectures 11, 14, 15 and 16) remain only in that Temp directory; there
is no corpus manifest, label or model score. Its `failure.json` is preserved.
No retry, Gemini request, private Knowledge read, database write or Ask policy
change followed. The retained volume, root `.env` and original PDF archives
remain untouched.

## Cause and source prequalification

The fifth selected PDF was [lecture 18](https://courses.grainger.illinois.edu/ece448/sp2020/slides/lec18.pdf).
Its first page explicitly states CC BY **3.0**, so the script's CC BY **4.0**
guard correctly rejected it. [Lecture 19](https://courses.grainger.illinois.edu/ece448/sp2020/slides/lec19.pdf)
also states CC BY 3.0 on its first page. This was a preregistration mistake,
not a parser failure or model-quality observation. To avoid another known
license mismatch, the new roster also replaces lectures 20, 21 and 36, whose
first-page licenses could not be independently confirmed through the public
PDF reader, with lectures whose first pages do state CC BY 4.0. The
[official schedule](https://courses.grainger.illinois.edu/ece448/sp2020/lectures.html)
links all chosen PDFs. The source text check was read-only; the new PDF bytes,
size and pypdf license extraction must still pass the guarded acquisition.

The new, immutable `v3` corpus ID has train `10,11,14,15,16,28`, calibration
`22,27,31,32`, heldout `25,26,33,38`; release holdout `17,37` remains
excluded. Its canonical preregistration SHA-256 is
`ee050f83d107c59cea09b2140f7cec81047684a9192d26ac7517a0753edfa881`,
verified locally without network. The limits remain 18 registered URLs,
24 GETs including redirects, 120 MiB received, 10 MiB and 100 pages per PDF,
30 minutes, exact first-page CC BY 4.0 and usable extracted text. A new
one-shot authorization and unused Temp output directory are required before
another acquisition. The failed directories must not be resumed or deleted
to disguise their receipts.

This audit still has no independently reviewed 192-group fixture or scoring.
The Mixedbread model passed load-only resource admission separately; its
reading-usefulness quality is unknown. Ask remains disabled and Lane 6 quality
boxes remain open.
