# Cohnsoft shared web platform rebrand

The user authorized the full company rebrand and production deployment, superseding the earlier pilot-only/no-deployment gate. Product names use the full **Cohnsoft** prefix. Six Nights at Banshee's retains its game title; Zephyr Rentals retains its business identity with “Built by Cohnsoft” attribution in its own repository.

## Inventory and risk plan

The active product hub is on `altstack/ecosystem-20261024`, not main. Baseline: `569e3f8a0176053eaac80402800b4266baea1ce0`, including the already-published Banshees download page changes. A separate checkout protects the other chat's local game and hub work.

Changes cover the launcher, Social, account/SSO display strings, company page, download pages, sharing/export cards, PWA metadata, fonts, colour tokens and product artwork. Canonical Cohnsoft assets are copied unchanged from `cohnsoftassets@752e894f90f1e58e62ae466352cb03c8bfd7d703`; SHA-256 provenance is in the vendored manifest. Original product icons were authored and exported through Cohnsoft Sprite; editable sources and provenance are included.

Do not change: PDS identity/handles, API endpoints, OAuth client IDs, environment variable names/values, cookies, local storage keys, database tables/files, repository names, existing release names/tags, published installer URL filters, storage/account/billing rules or third-party notices. Existing installer filenames are intentionally still exposed through the verified release catalogue. No data migration is required because no user storage path changes.

`/artemis` redirects permanently to `/cohnsoft`. Existing application routes and icon endpoints remain supported. New local brand routes use an explicit manifest allowlist rather than arbitrary filesystem serving. The existing PWA ID/start URL remains `/`; its cache is updated without caching accounts, APIs or documents.

The future `cohnsoft.com` main-site and `cohn.social` PDS domain changes remain deferred. The PDS needs an identity-preserving migration, not hostname substitution.

## Validation record

The local full suite passes all 85 tests. Browser evidence is saved in `screenshots/cohnsoft/`; the company page, launcher and Social were exercised with the full Cohnsoft names and local brand assets. Tests exercise real local server processes, account/session preservation, API boundaries, legacy download filtering, canonical asset integrity, editable icon compatibility, static branding routes and safe asset access. macOS/Windows/Linux installers are not rebuilt by this web-only PR; those are separate repository tasks.
