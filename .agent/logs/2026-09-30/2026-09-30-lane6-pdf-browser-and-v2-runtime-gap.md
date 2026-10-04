# Lane 6 local PDF browser and v2 runtime gap

Date: 2026-09-30 (America/Chicago). Starting checkout: `main` at `6c02d6c`.
This was a read-only local-stack and browser check plus a source audit. It used
no Gemini request, provider key, private PDF export, database mutation or Ask
activation. The populated database volume, root `.env`, attached originals and
existing uncommitted work were preserved.

`docker compose ps --format json` through the normal approved local Docker
path showed healthy API, frontend, database, index, generation, answer and
email workers. An initial sandbox-only probe had lacked Docker pipe access;
the approved read-only retry succeeded. In the authenticated in-app browser,
the Subject showed Ask disabled with the source-only disclosure. The Published
lectures browser opened the **original PDF page 1** for Week 2 (33 pages),
Week 3 (42 pages) and Week 4 (32 pages); Week 2 advanced to PDF page 2. Each
page rendered the PDF image with page counter and readable/extracted text
controls, rather than the earlier PDF-error fallback. This establishes only
these observed local browser paths, not every page or a spoken assistive
technology pass. No page contents are copied into this log.

The independent source audit found that the new, inert public
`public_exhaustive_page_and_cue_v2` prototype sends a cue-first, four-page
request. The retained answer worker still uses the v1 source-ID prompt,
page-first REST serialization and the v4/Gemini 3.8 profile. Simply opening
the current Ask flag would execute a different, unvalidated request. A future
public v2 pass therefore still needs a versioned runtime policy and prompt,
an exactly matching REST body, new Alembic constraints after used revision
`0029`, typed API/client disclosure, and retained v4 read semantics while
fencing old retries. The current runtime may send a different candidate
composition from the four-page public test; a private original-PDF measurement
remains necessary. This audit changed no runtime source.

The 96-group fresh public source set has not yet been authored and independently
reviewed. Its calibration and heldout are unscored. The earlier public pilot
failed a no-useful gate. Ask remains disabled, and Lane 6 is still 3/7.
