# Render the Amerika SDDM theme with the real greeter in test mode and save a screenshot (the theme has a development hook).
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
rm -rf $T/theme && cp -r $ROOT/src/os/login/amerika $T/theme
printf '[General]\nscreenshot=%s\n' "$ROOT/dist/login-shot.png" > $T/theme/theme.conf.user
rm -f $ROOT/dist/login-shot.png
QT_QPA_PLATFORM=wayland timeout 40 sddm-greeter-qt6 --test-mode --theme $T/theme > $T/greeter.log 2>&1
echo "greeter exit: $?"
