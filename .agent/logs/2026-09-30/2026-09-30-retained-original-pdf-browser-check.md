# Retained local original-PDF browser check

Date: 2026-09-30 (America/Chicago). Scope: read-only authenticated browser
inspection of the retained local installation while Lane 6 Ask is disabled.
No account mutation, provider call, `.env` read or database write occurred.

The tester opened the current Subject's published-lecture viewer in a
temporary in-app browser tab. Week 2, Week 3 and Week 4 original PDF page 1
each visibly rendered, with respective page counts **33, 42 and 32** and no
extracted-text fallback warning. Week 2's Next control advanced to page
2/33. At a 390×844 viewport, Week 4's dialog, PDF and controls fit without
visible horizontal overflow. Keyboard Return on its focused list button
opened the dialog; Tab reached its controls without focus escaping; both the
PDF readable text and extracted-page-text disclosures could be opened by
keyboard. Escape closed the dialog and returned focus to the lecture button.
The viewport was reset and the temporary tab closed afterward.

The Ask panel displayed **“Knowledge search is paused”**; New conversation,
Question and Ask were disabled. This confirms the observed browser fence on
this path, not every backend authorization state. Slide text appeared small
on the mobile viewport, while the keyboard-accessible extracted text gave an
alternative; this is a usability observation, not a spoken accessibility
pass.

This check is **not** the Lane 6 release gate. It did not exercise a live Ask
result or no-match, access revocation while the PDF dialog is open,
cross-Subject/private-source denial, or manual no-mouse spoken
NVDA/Narrator verification. The [accessibility guide](../../docs/ACCESSIBILITY.md)
still requires the spoken packaged-candidate check and correct dialog/focus
behavior under revoked access. Ask remains disabled and Lane 6 remains 3/7.
