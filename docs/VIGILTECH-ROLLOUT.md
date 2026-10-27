# VigilTech rollout and Icons & Wallpapers

This is a review branch. No deployment or merge is authorized by this PR. The supplied VigilTech brief supersedes earlier company identities. The wider repository rebrand is incomplete; existing Cohnsoft pages and technical IDs are still present outside the new gallery and company preview.

## Icons & Wallpapers

Routes: `/icons-wallpapers`, `/assets-collection/catalog.json`, `/assets/download/:id`, `/assets/preview/:id`. Linked from the workspace navigation, download navigation and company page. `/vigiltech` is the initial company preview; it does not replace the live root page yet.

Source: danecohn/ios27icons at 2d9531e89a6c5847685de4d7012903ff5e9cfcba. All 416 PNGs are included in the catalogue: 160 icons in Night and Rose (320), six wallpapers and 90 widget covers. Their original names and attribution remain. The user explicitly approved including the whole pack, including recognisable third-party marks and faith-themed artwork, as an exception to the general branding exclusions. This exception applies to the collection, not unrelated product copy.

Search, category and appearance filters, progressively revealed results, accessible modal previews, individual full-resolution downloads, original-source ZIP and supplied installation instructions are included. PNGs are fetched from exact, pinned paths; every preview and download is checked for exact byte length and SHA256 before sending. IDs are allowlisted, unknown IDs cannot become arbitrary URLs, upstream redirects are rejected and time/size bounds apply. A 32 MiB process cache reduces repeat requests. Existing CSP is unchanged. A temporary source failure produces a retry message; the complete source ZIP is linked separately. No accounts, analytics, sounds or credentials are involved.

VigilTech assets and font binaries are copied unchanged from cohnsoftassets at 5baba6f; shared CSS includes review commit fe61522 (assets PR 1). UPSTREAM.json records SHA256 hashes. No new logos were drawn. Sound remains off; this gallery does not use audio.

## Verification

- `node --test test/*.test.mjs`: 88 pass, zero failures/skips.
- New catalogue/download tests verify counts, unique IDs, content hashes, invalid IDs/methods, HEAD behaviour and refusal of tampered source bytes.
- Actual local HTTP PNG download: Phone 274736 bytes; Candlelight wallpaper 1632251 bytes; preview 40978 bytes, correct attachment/inline headers.
- Real WebKit: search, modal open/close, six wallpaper matches and 90 cover matches, Night/Dawn, 1280px desktop and 390px phone. Both widths have no horizontal overflow. Original hero images load through the restricted same-origin route.
- Screenshot evidence: docs/review/vigiltech/gallery-{night,dawn}-{desktop,phone}.png.
- No production deployment, installer, platform build, macOS notarization or new domain connection was performed.

## Remaining rebrand

Shared CSS PR: https://github.com/danecohn/cohnsoftassets/pull/1. Continue with Search, this site's remaining screens/server naming/metadata and compatibility redirects, Office, Mail/Calendar, Drive, Journal, Game Producer, Lookout, Notes, Prompter, creative tools and Social native/mobile clients, Venture, OS, base search and publisher-only game attribution. Zephyr's business and the family portal retain their identities while their publisher attribution changes.

Do not silently relicense upstream code. Search/SearXNG requires AGPL notices and a compatible distribution licence. Audit other dependencies and their existing notices before GPL updates. New first-party gallery modules use GPL-3.0-or-later; supplied artwork's GPL and the font's OFL are preserved.

App/package/bundle ID changes requested in the new brief need platform-specific migration and update-feed validation. Existing data directories, authentication/storage keys, licences, repositories and historical releases must remain recoverable. Domain vigiltech.org and new email endpoints are not yet connected; do not invent working services. No direct main pushes.
