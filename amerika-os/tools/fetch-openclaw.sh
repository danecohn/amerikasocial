#!/usr/bin/env bash
# Stage the pinned OpenClaw engine for the amerika-agent package.
#
#   tools/fetch-openclaw.sh [--out DIR] [--cache DIR] [--node-bin DIR] [--offline] [--force] [--keep-cua]
#   tools/fetch-openclaw.sh --update-lock VERSION     # re-pin to another openclaw release (see docs/agent/README.md)
#
# Inputs (committed):  src/os/agent/{package.json,package-lock.json,openclaw.lock.json}
# Output:              DIR/node_modules/openclaw/...  (a pruned, verified, linux-arm64 install; default work/openclaw-src/stage-amerika)
#
# Reproducibility: `npm ci` installs exactly what package-lock.json says and verifies every tarball against the
# SHA-512 integrity recorded there; openclaw.lock.json additionally pins the integrity of the openclaw tarball itself and
# the SHA-256 of package-lock.json, and this script refuses to continue if either differs.
# Network: only used when the npm cache in CACHE/npm does not yet hold a package. With a populated cache (or
# --offline / AMERIKA_OFFLINE=1) nothing is downloaded. A finished stage is reused when its stamp matches the inputs.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
WORK="$(dirname "$REPO")"
AGENT_SRC="$REPO/src/os/agent"
LOCK="$AGENT_SRC/openclaw.lock.json"

OUT="${AMERIKA_OPENCLAW_OUT:-$WORK/openclaw-src/stage-amerika}"
CACHE="${AMERIKA_OPENCLAW_CACHE:-$WORK/openclaw-src/cache}"
NODE_BIN="${AMERIKA_NODE_BIN:-$WORK/tools/node/bin}"
OFFLINE="${AMERIKA_OFFLINE:-0}"
FORCE=0
KEEP_CUA=0
UPDATE_LOCK=""

die() { echo "fetch-openclaw: $*" >&2; exit 1; }
log() { echo "fetch-openclaw: $*" >&2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --cache) CACHE="$2"; shift 2 ;;
    --node-bin) NODE_BIN="$2"; shift 2 ;;
    --offline) OFFLINE=1; shift ;;
    --force) FORCE=1; shift ;;
    --keep-cua) KEEP_CUA=1; shift ;;
    --update-lock) UPDATE_LOCK="$2"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

if [ -x "$NODE_BIN/node" ]; then export PATH="$NODE_BIN:$PATH"; fi
command -v node >/dev/null || die "node not found (set AMERIKA_NODE_BIN)"
command -v npm >/dev/null || die "npm not found next to node"
command -v python3 >/dev/null || die "python3 not found"

NODE_V="$(node -p 'process.versions.node')"
python3 - "$NODE_V" <<'PY' || die "node $NODE_V does not satisfy the OpenClaw engine range (>=24.16 <25)"
import sys
v = tuple(int(x) for x in sys.argv[1].split('.')[:3])
sys.exit(0 if (24, 16, 0) <= v < (25, 0, 0) else 1)
PY

OUT="$(realpath -m "$OUT")"; CACHE="$(realpath -m "$CACHE")"
mkdir -p "$CACHE/npm"
NPM_COMMON=(--omit=dev --no-audit --no-fund --ignore-scripts --update-notifier=false --os=linux --cpu=arm64 --libc=glibc --cache "$CACHE/npm")

# ---------------------------------------------------------------------------------------------------------------- re-pin
if [ -n "$UPDATE_LOCK" ]; then
  [ "$OFFLINE" = 1 ] && die "--update-lock needs the network"
  log "re-pinning openclaw to $UPDATE_LOCK"
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  python3 - "$AGENT_SRC/package.json" "$tmp/package.json" "$UPDATE_LOCK" <<'PY'
import json, sys
src, dst, ver = sys.argv[1:4]
d = json.load(open(src))
d['dependencies'] = {'openclaw': ver}
json.dump(d, open(dst, 'w'), indent=2)
open(dst, 'a').write('\n')
PY
  (cd "$tmp" && npm install --package-lock-only "${NPM_COMMON[@]}" >/dev/null)
  (cd "$tmp" && npm pack "openclaw@$UPDATE_LOCK" --silent --pack-destination "$CACHE" >/dev/null)
  python3 - "$LOCK" "$tmp" "$CACHE/openclaw-$UPDATE_LOCK.tgz" "$UPDATE_LOCK" <<'PY'
import base64, datetime, hashlib, json, sys
lock_path, tmp, tgz, ver = sys.argv[1:5]
lock = json.load(open(lock_path))
pl_bytes = open(f'{tmp}/package-lock.json', 'rb').read()
entry = json.loads(pl_bytes)['packages']['node_modules/openclaw']
data = open(tgz, 'rb').read()
integ = 'sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode()
if entry['integrity'] != integ or entry['version'] != ver:
    sys.exit('registry metadata and downloaded tarball disagree; refusing to pin')
pkg = json.loads(__import__('subprocess').check_output(['tar', '-xzOf', tgz, 'package/package.json']))
lock.update(version=ver, resolved=entry['resolved'], integrity=integ, tarball_sha256=hashlib.sha256(data).hexdigest(),
            tarball_bytes=len(data), license=pkg.get('license', ''), node_engines=pkg.get('engines', {}).get('node', ''),
            package_lock_sha256=hashlib.sha256(pl_bytes).hexdigest(), locked=datetime.date.today().isoformat())
json.dump(lock, open(lock_path, 'w'), indent=2)
open(lock_path, 'a').write('\n')
PY
  cp "$tmp/package.json" "$AGENT_SRC/package.json"
  cp "$tmp/package-lock.json" "$AGENT_SRC/package-lock.json"
  log "updated $LOCK, package.json and package-lock.json. Review the diff, then re-run the verification list in docs/agent/README.md."
  exit 0
fi

# ---------------------------------------------------------------------------------------------------------------- verify pins
LOCK_VERSION="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$LOCK")"
python3 - "$LOCK" "$AGENT_SRC" <<'PY' || die "pin files are inconsistent (see message above)"
import hashlib, json, sys
lock = json.load(open(sys.argv[1]))
base = sys.argv[2]
pl_bytes = open(f'{base}/package-lock.json', 'rb').read()
if hashlib.sha256(pl_bytes).hexdigest() != lock['package_lock_sha256']:
    sys.exit('package-lock.json does not match openclaw.lock.json (package_lock_sha256)')
entry = json.loads(pl_bytes)['packages']['node_modules/openclaw']
if entry['version'] != lock['version'] or entry['integrity'] != lock['integrity']:
    sys.exit('package-lock.json openclaw entry does not match openclaw.lock.json')
pkg = json.load(open(f'{base}/package.json'))
if pkg['dependencies'].get('openclaw') != lock['version']:
    sys.exit('package.json must pin the exact openclaw version')
PY

STAMP_WANT="$(python3 - "$LOCK" "$AGENT_SRC/package-lock.json" "$0" "$KEEP_CUA" <<'PY'
import hashlib, sys
h = hashlib.sha256()
for p in sys.argv[1:4]:
    h.update(open(p, 'rb').read())
h.update(sys.argv[4].encode())
print(h.hexdigest())
PY
)"
if [ "$FORCE" = 0 ] && [ -f "$OUT/.amerika-stamp" ] && [ "$(cat "$OUT/.amerika-stamp")" = "$STAMP_WANT" ] \
   && [ -f "$OUT/node_modules/openclaw/openclaw.mjs" ]; then
  log "stage is current: $OUT (openclaw $LOCK_VERSION)"
  echo "$OUT"
  exit 0
fi

# ---------------------------------------------------------------------------------------------------------------- tarball check
TGZ="$CACHE/openclaw-$LOCK_VERSION.tgz"
if [ ! -f "$TGZ" ] && [ "$OFFLINE" != 1 ] && [ ! -d "$CACHE/npm/_cacache" ]; then
  log "downloading openclaw@$LOCK_VERSION"
  npm pack "openclaw@$LOCK_VERSION" --silent --pack-destination "$CACHE" --cache "$CACHE/npm" >/dev/null
fi
if [ -f "$TGZ" ]; then
  python3 - "$LOCK" "$TGZ" <<'PY' || { rm -f "$TGZ"; die "cached openclaw tarball failed its checksum and was removed; re-run"; }
import base64, hashlib, json, sys
lock = json.load(open(sys.argv[1]))
data = open(sys.argv[2], 'rb').read()
ok = ('sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode() == lock['integrity']
      and hashlib.sha256(data).hexdigest() == lock['tarball_sha256'])
sys.exit(0 if ok else 1)
PY
  log "tarball checksum OK ($(basename "$TGZ"))"
fi

# ---------------------------------------------------------------------------------------------------------------- install
rm -rf "$OUT.tmp"; mkdir -p "$OUT.tmp"
cp "$AGENT_SRC/package.json" "$AGENT_SRC/package-lock.json" "$OUT.tmp/"
cd "$OUT.tmp"
if ! npm ci "${NPM_COMMON[@]}" --offline >/dev/null 2>"$OUT.tmp/npm-offline.log"; then
  [ "$OFFLINE" = 1 ] && { cat "$OUT.tmp/npm-offline.log" >&2; die "npm cache $CACHE/npm is incomplete and --offline was given"; }
  log "npm cache incomplete, fetching the missing packages (integrity-checked against package-lock.json)"
  rm -rf node_modules
  npm ci "${NPM_COMMON[@]}" --prefer-online >/dev/null
fi
rm -f npm-offline.log

PKG="$OUT.tmp/node_modules/openclaw"
[ -f "$PKG/openclaw.mjs" ] || die "openclaw was not installed"
python3 - "$LOCK" "$OUT.tmp/node_modules/.package-lock.json" <<'PY' || die "installed openclaw does not match the pinned integrity"
import json, sys
lock = json.load(open(sys.argv[1]))
e = json.load(open(sys.argv[2]))['packages']['node_modules/openclaw']
sys.exit(0 if (e['integrity'] == lock['integrity'] and e['version'] == lock['version']) else 1)
PY

# ---------------------------------------------------------------------------------------------------------------- lifecycle (the ones that matter)
# `npm ci --ignore-scripts` skipped every package script on purpose (arbitrary code from 560 packages). What the install
# scripts would have done, and what we still need:
#   openclaw  postinstall  -> scripts/postinstall-bundled-plugins.mjs: prunes stale dist files against
#                             dist/postinstall-inventory.json, verifies the @openclaw/fs-safe native prebuild (present: no network)
#                             and clears the lifecycle marker. RUN EXPLICITLY below.
#   koffi     install      -> cnoke --prebuild: only fetches a prebuilt .node if the platform package is missing. The
#                             @koromix/koffi-linux-arm64 package is installed, so nothing to do; verified by require() below.
#   esbuild   postinstall  -> optimises the CLI launcher; the JS API finds @esbuild/linux-arm64 by itself. Skipped.
#   protobufjs postinstall -> checks the version scheme of a CLI helper. Skipped.
#   @google/genai          -> no-op echo scripts.
log "running openclaw's own postinstall step"
( cd "$PKG" && HOME="$OUT.tmp/.home" OPENCLAW_STATE_DIR="$OUT.tmp/.home/state" node scripts/postinstall-bundled-plugins.mjs ) \
  || die "openclaw postinstall step failed"
rm -rf "$OUT.tmp/.home"

# ---------------------------------------------------------------------------------------------------------------- prune
log "pruning"
before="$(du -sk node_modules | cut -f1)"
python3 - "$OUT.tmp/node_modules" "$KEEP_CUA" <<'PY'
import os, re, shutil, sys
root, keep_cua = sys.argv[1], sys.argv[2] == '1'
removed = 0

def rm(path):
    global removed
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)
    removed += 1

# 1. platform packages and prebuild directories for anything that is not linux-arm64 (glibc)
KEEP_RE = re.compile(r'linux-arm64(-gnu)?$')
OTHER_PLATFORM = re.compile(r'(^|[-_])(darwin|win32|windows|freebsd|openbsd|netbsd|android|sunos|aix|openharmony|linux-(x64|x86|ia32|arm|riscv64|ppc64|s390x|loong64|mips64el)|musl)([-_.]|$)', re.I)
for scope_or_pkg in sorted(os.listdir(root)):
    p = os.path.join(root, scope_or_pkg)
    names = [(scope_or_pkg, p)] if not scope_or_pkg.startswith('@') else [
        (scope_or_pkg + '/' + n, os.path.join(p, n)) for n in sorted(os.listdir(p))]
    for name, path in names:
        base = name.split('/')[-1]
        if OTHER_PLATFORM.search(base) and not KEEP_RE.search(base):
            rm(path)
for dirpath, dirnames, _ in os.walk(root):
    if os.path.basename(dirpath) == 'prebuilds':
        for d in list(dirnames):
            if not d.startswith('linux-arm64'):
                rm(os.path.join(dirpath, d)); dirnames.remove(d)
        dirnames[:] = []

# 2. source maps and TypeScript declaration files of dependencies (never loaded at run time); the openclaw package keeps its own
oc = os.path.join(root, 'openclaw')
for dirpath, dirnames, filenames in os.walk(root):
    # inside the openclaw package proper (not its nested node_modules) only maps are removed
    only_maps = dirpath == oc or (dirpath.startswith(oc + os.sep) and not dirpath.startswith(os.path.join(oc, 'node_modules')))
    for f in filenames:
        full = os.path.join(dirpath, f)
        if f.endswith('.map') or (not only_maps and re.search(r'\.d\.(c|m)?ts$', f)):
            rm(full)

# 3. bundles that only serve features Amerika Agent does not enable
unneeded = [
    'openclaw/dist/worker-artifacts',   # cloud-worker bundles (nodeHost.workerRuns / cloudWorkers), off in Amerika
]
if not keep_cua:
    unneeded += ['@trycua/cua-driver-linux-arm64-gnu']  # native macOS/Windows/Linux GUI-driver runtime (optional dependency); Amerika uses amerika-mcp
for rel in unneeded:
    path = os.path.join(root, rel)
    if os.path.exists(path):
        rm(path)

# 4. empty directories
for dirpath, dirnames, filenames in os.walk(root, topdown=False):
    if not os.listdir(dirpath) and dirpath != root:
        os.rmdir(dirpath)
print(f'pruned {removed} entries', file=sys.stderr)
PY
after="$(du -sk node_modules | cut -f1)"
log "node_modules: $((before / 1024)) MB -> $((after / 1024)) MB"

# ---------------------------------------------------------------------------------------------------------------- smoke
log "smoke test"
SMOKE_HOME="$(mktemp -d)"
trap 'rm -rf "$SMOKE_HOME"' EXIT
export HOME="$SMOKE_HOME" OPENCLAW_STATE_DIR="$SMOKE_HOME/state" OPENCLAW_CONFIG_PATH="$SMOKE_HOME/openclaw.json" OPENCLAW_NO_UPDATE_CHECK=1
ver_out="$(node "$PKG/openclaw.mjs" --version)"
case "$ver_out" in *"$LOCK_VERSION"*) ;; *) die "openclaw --version printed '$ver_out', expected $LOCK_VERSION" ;; esac
( cd "$OUT.tmp" && node -e "const k=require('koffi'); if(!k.version) process.exit(1)" ) || die "koffi native module does not load"
( cd "$OUT.tmp" && node --input-type=module -e "
  import { createRequire } from 'node:module';
  const r = createRequire(process.cwd() + '/node_modules/openclaw/package.json');
  const { configureFsSafeNative } = await import(r.resolve('@openclaw/fs-safe/config'));
  configureFsSafeNative({ mode: 'require' });
  const { readCloneFileMetadata } = await import(r.resolve('@openclaw/fs-safe/copy'));
  await readCloneFileMetadata([]);
" ) || die "@openclaw/fs-safe native binding does not load"
node "$PKG/openclaw.mjs" config validate >/dev/null 2>&1 || true   # no config in the throwaway HOME: only checks that the CLI boots
node "$PKG/openclaw.mjs" --help >/dev/null || die "openclaw --help failed"
unset HOME OPENCLAW_STATE_DIR OPENCLAW_CONFIG_PATH OPENCLAW_NO_UPDATE_CHECK
rm -rf "$SMOKE_HOME"

echo "$STAMP_WANT" > "$OUT.tmp/.amerika-stamp"
rm -rf "$OUT"
mv "$OUT.tmp" "$OUT"
log "staged openclaw $LOCK_VERSION at $OUT"
echo "$OUT"
