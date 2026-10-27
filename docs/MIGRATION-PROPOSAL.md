# Compatibility migration proposal — owner approval required

Status: proposed only. None of these identity, storage, feed, filename or repository migrations have been applied. Visible product names can be VigilTech while technical identifiers remain compatible.

## Recommended decision for this release

Keep every existing identifier and storage location. This avoids creating new empty profiles, losing OS permissions or breaking update clients. Publish the visible rebrand with the existing download filenames. New installer formats are additive.

| Area | Current compatibility contract | Proposed later migration | Recovery |
| --- | --- | --- | --- |
| Native IDs (`com.amerika.*`, `org.altstack.*`, `com.artemissoftworks.*`, `social.amerika.*`) | Keep exact IDs, signing requirements, keychain groups and installed shortcuts | Inventory each binary first. Prefer retaining IDs permanently; if changed, ship a separately approved per-app importer and test upgrades on both architectures | Retain old app and untouched profile; do not uninstall automatically |
| Browser storage and preferences | Keep localStorage/IndexedDB/Qt/Expo keys and cookie scopes | Versioned reader accepts old and new keys; copy with checksum and completion marker only after successful read | Continue reading old keys if verification fails; never delete originals |
| `~/AltStack`, Artemis folders and Office shared storage | Preserve existing data paths and mount names | Opt-in copy into a new directory after free-space check and verified backup; lock against simultaneous writers; check symlinks/ownership, collisions and byte hashes | Keep source and backup, switch configuration back; no automatic cleanup |
| `ALTSTACK_*` / `AMERIKA_*` environment variables | Existing names stay authoritative | Introduce documented aliases only after inventory; explicit new name wins, old remains fallback with a warning containing names, never values | Remove new aliases to return to old behavior |
| Update feeds and artifact names | Existing URLs, release tags and filenames remain valid | Prefer retaining feeds indefinitely; any eventual redirect must be tested by each actual updater, with signed metadata and downgrade policy retained | Serve old manifest/artifacts until all supported versions have migrated |
| Repository names | Existing repos and upstream license histories retained | `cohnsoftassets` → `vigiltechassets` is a candidate only. Map CI, Railway source, submodules, badges and asset provenance before any rename | Retain GitHub redirect, update consumers in PRs, revert consumer changes if a source disconnects |
| Company and account domains | `vigiltech.org` hosts public company content; existing app/account/PDS origins continue | Any account or PDS domain move needs its own DID/OAuth/cookie/passkey/redirect and backup plan | Existing origin remains available; no account database relocation |

Before requesting approval for a particular migration, attach its exact old/new mapping, backups and restore drill, representative upgrade tests, failure behavior, disk-space budget and rollback commands. A blanket rename is not proposed. Do not apply this document as permission.

Excluded entirely: cohnemail, zephyrrentals and banshees. Canonical supplied asset files and upstream notices remain unchanged.
