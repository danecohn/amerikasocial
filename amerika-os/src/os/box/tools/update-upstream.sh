#!/bin/bash
# Rebuild src/os/box/app/{beepbox_editor,beepbox_synth}.min.js from upstream BeepBox plus our patches/*.patch.
# Usage: update-upstream.sh [COMMIT]   (default: the commit pinned in beepbox.lock.json)
# Needs git, network, and Node (set NODE_BIN to the folder holding node/npm; default ../tools/node/bin of the repo).
# Updating upstream: run with a new commit; if a patch fails, fix it in the scratch clone it prints, `git format-patch`
# the result into patches/, then update beepbox.lock.json (commit, tarball_sha256 via the printed hash).
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PATH="${NODE_BIN:-$ROOT/../tools/node/bin}:$PATH"
COMMIT=${1:-$(python3 -c "import json;print(json.load(open('$HERE/beepbox.lock.json'))['commit'])")}
WORK=$(mktemp -d)
echo "scratch: $WORK"
git clone -q https://github.com/johnnesky/beepbox.git "$WORK/bb"
cd "$WORK/bb"
git checkout -q "$COMMIT"
curl -sL -o "$WORK/src.tar.gz" "https://codeload.github.com/johnnesky/beepbox/tar.gz/$COMMIT"
echo "tarball sha256: $(sha256sum "$WORK/src.tar.gz" | cut -d' ' -f1)"
git config user.email box@amerika.invalid; git config user.name "AltStack Box"
git am -q "$HERE"/patches/*.patch
npm ci --ignore-scripts >/dev/null
npm run build-synth >/dev/null
npm run build-editor >/dev/null
cp bundle/beepbox_editor.min.js bundle/beepbox_synth.min.js "$HERE/app/"
cp LICENSE.md "$HERE/LICENSE-BeepBox.md"
echo "updated app/*.min.js from $COMMIT; now update beepbox.lock.json hashes and run the tests"
