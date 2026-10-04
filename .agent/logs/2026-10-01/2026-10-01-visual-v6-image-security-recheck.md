# Current v6 release-image security verification

## Scope and preservation

Rechecked the actual 0031/v6 backend and frontend images, plus a separately
built matching OCR-enabled backend. The running services, populated database,
original PDFs and root configuration were unchanged. Preserved the previous
aggregate reports under `artifacts/security-before-v6-20261001` before the
documented isolated security harness wrote a fresh report directory.

## Checks actually completed

- Standard backend: `sha256:cc8b320c642682aadeebda089aca00f5736dff065c3336486190bbcfece1d5fb`.
- OCR backend: `sha256:6fa2427d630c10e1ba8ed2b8f081501dcd90cd77fede2b52642bbe673a9cccb4`.
- Frontend: `sha256:137ec39c9b5fea1937f5422b03a83555abd2dd9d166727d05392649da68869ec`.
- `scripts/test_security.py --image-tag lane6-v6-security` passed all gates:
  isolated Git/history and worktree secret scans, HIGH/CRITICAL vulnerability
  checks on all three immutable images, CycloneDX SBOMs and report checksums.
  The Gitleaks scan covered 93 commits and reported no leaks. Public advisory
  acquisition occurred before source or image bytes were mounted; actual
  scans ran with Docker networking disabled. Operator data/secrets were not
  copied into the isolated Git-visible snapshot.
- Networkless `scripts/check_images.py` probes passed for all three variants:
  backend native dependencies/API/workers/auth/AES-GCM/PDF/bounded original-page
  PNG; OCR variant additionally image-only PDF OCR and English data; frontend
  non-root UID, Nginx/health/assets/PDF module worker, branding/error behavior,
  security/cache headers and private-target log redaction.

The source snapshot is the dirty working tree at HEAD `6c02d6c`; its isolated
security snapshot commit is `24c6de8e26c45d0957783433fd0d9fcaa046dbc1`.
It is not a repository commit, PR, hosted CI or release. Reports remain ignored
under `artifacts/security`; generated scanner source/history/image archives
and smoke containers were cleaned. Local candidate image tags remain for
reproducibility. No provider calls, private Knowledge transfer or Ask
enablement occurred. Independent heldout/private usefulness and spoken
assistive-technology gates remain open.
