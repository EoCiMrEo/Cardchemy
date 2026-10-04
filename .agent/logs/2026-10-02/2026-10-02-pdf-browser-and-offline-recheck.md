# Browser PDF regression and full offline recheck

The retained application remains at head 0031, Ask/source judging disabled.
Opened a background in-app-browser tab against the running local application;
existing authentication restored without credential entry. Published-lecture
browsing remains available while Ask controls correctly remain disabled.

Opened an attached original lecture PDF through the published-lectures UI.
The original page rendered visibly with the PDF page counter and previous/next
controls; no original-PDF failure fallback appeared. Enter on Next PDF page
rendered page two; Escape closed the named dialog and returned focus to its
original lecture trigger. Readable PDF text and extracted-text alternatives
were exposed in the accessibility tree. The observed 1,280-pixel viewport
contained the dialog without document horizontal overflow. No Ask submission,
provider call, content mutation or data cleanup occurred in this UI check.

This verifies actual local original-PDF opening and keyboard/accessibility-tree
behavior. It is **not spoken assistive-technology evidence**. No screenshot or
lecture content is stored in the repository. The previous dated three-original
page-opening evidence remains preserved.

Full backend offline recheck completed with **3,836 passed, 181 skipped and
two deselected**, 286.48 seconds, exit zero. This includes the new private query
caller and public remaining46 contracts, and was collected before any
prospective subject-anchor tests. Separate targeted runs passed 107 private
caller/builder contracts and 67 public continuation/historical contracts.
No hosted CI, new disposable DB/migration, fresh image scan or final release
completion is implied by these offline results. Context validation passed
37 required files, 79 active guides and 1,889 local links before the latest logs.
Ask remains disabled and Lane 6 remains **3/7**.
