# Archive key lifecycle

Current archive fingerprint: `9F52BD98A8EE9096B1BE7AAC1063BBC989A11133`.
The checked-in files under `flavor/keys` are public exports. Private signing material stays only in the user's existing
local signing home, never in source, packages, a served repository, ISO or CI secrets collected by this task.

Routine builds use that existing identity. `--no-repo` does not access it. An absent key stops signed repository
creation; it is not a reason to generate or reconstruct another key. No rotation was performed for this development build.

A future rotation requires an explicit owner decision. Prepare a new public key in a controlled environment, verify
its full fingerprint through an independent channel, ship an overlapping keyring update signed by the old identity,
wait for installed clients to receive it, and only then sign releases with the new identity. Keep old-key verification
available for a documented overlap/recovery period. Test gpgv and a fresh isolated APT root before public publication.
Do not publish a key-only recovery that asks users to disable signature verification or use `trusted=yes`.

If a key is compromised, pause publication, identify the affected release/package hashes, publish the incident and a
verified recovery path, and treat clients that accepted malicious packages as potentially compromised. Expiration or
key loss is not proof of compromise, but it still requires an authenticated migration. Actual key-generation, revocation
and signing commands are intentionally excluded from an unattended development workflow.
