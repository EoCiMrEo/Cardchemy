# Frontend PCRE2 image repair — 2026-10-01

## Scope and starting context

- Started from source HEAD `6c02d6cf063acf83f4da5c08cfc4a3aa2c94be57` with extensive pre-existing local changes; preserved them.
- The existing aggregate security report identified one HIGH frontend image finding: `CVE-2026-103111` in Alpine `pcre2` `10.48-r0`, with `10.49-r0` as the fixed package. The four separate `generic-api-key` history findings were outside this repair and were not inspected for content here.
- The [PCRE2 maintainer advisory](https://github.com/PCRE2Project/pcre2/security/advisories/GHSA-r9hj-j2rw-4q3m) marks 10.49 fixed. The [Alpine 3.24 x86_64 repository](https://dl-cdn.alpinelinux.org/alpine/v3.24/main/x86_64/) published `pcre2-10.49-r0`.

## Change

- `frontend/Dockerfile`: retained the pinned Node and Nginx images and existing `apk upgrade --no-cache`; added `apk add --no-cache 'pcre2>=10.49-r0'` so a stale Alpine mirror fails the build rather than producing a vulnerable runtime image.
- `docs/RUNTIMES.md`: documented the frontend runtime package floor and exact-image verification requirement.
- No npm dependency, frontend source, bundle budget, environment file, volume or running service was changed.

## Verification

- Compose development configuration: `docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile development config --quiet` passed with process `APP_VERSION=0.1.0`.
- Frontend-only no-cache build: `docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile development build --no-cache frontend` passed with process `APP_VERSION=0.1.0`. Build output showed `pcre2` upgraded from `10.48-r0` to `10.49-r0`; npm install reported zero npm vulnerabilities; the TypeScript/Vite production build passed.
- Exact built image: `sha256:c1702c8a414893e73479f780524b32d4ac4714530c1a3f90501799381aa3ab10`, `linux/amd64`, runtime UID/GID `101:101`, 48,685,639 bytes.
- Read the installed package database in that immutable image with network disabled: `pcre2-10.49-r0` installed.
- `python scripts/check_images.py frontend --image sha256:c1702c8a414893e73479f780524b32d4ac4714530c1a3f90501799381aa3ab10` passed the documented runtime smoke, including health, static assets/PDF worker, headers and private target log redaction.
- Exported the immutable image to a temporary archive and used the harness-pinned Trivy `0.70.0` image with the existing public advisory cache, `--network none`, `--offline-scan`, `--skip-db-update`, `--skip-java-db-update`, and HIGH/CRITICAL failure threshold. The targeted vulnerability scan exited 0 with zero HIGH/CRITICAL findings. A targeted CycloneDX 1.6 SBOM contained 22 components and recorded `pcre2` `10.49-r0`.

## Limits and cleanup

- This was a targeted frontend image repair. The complete three-image and Git-history security harness was not rerun. Its separate history findings remain for the parent task to resolve and verify.
- The frontend service was not recreated, so the running container was not claimed to use the new image.
- The temporary image archive and targeted scan reports under `.agent/.verification` were removed after checking their resolved path. The root `.env`, retained data and earlier aggregate report were preserved. No provider, private Knowledge or heldout calls were made.
