# Render every Settings page in the rig (fixture data, no real services) and save PNGs under dist/settings/.
# Usage: tools/kwin-rig.sh "sh tests/rig/settings_shots.sh [page ...]"
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export AMERIKA_ICONS=$ROOT/src/os/icons AMERIKA_WALLPAPERS=$ROOT/src/os/wallpapers AMERIKA_SCHEMES=$ROOT/src/os/color-schemes
export AMERIKA_SETTINGS_FAKE=1 AMERIKA_SETTINGS_SHOTS=$ROOT/dist/settings
mkdir -p "$AMERIKA_SETTINGS_SHOTS"
cd "$ROOT/src/os" && timeout 120 python3 -m amerika.settings
echo "settings exit: $?"
