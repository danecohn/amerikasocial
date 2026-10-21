# Amerika session environment for application defaults. Sourced (not executed) by amerika-session before KWin starts.
# POSIX sh. Every line is guarded so a missing optional package never breaks the session.
share=/usr/share/amerika-os

[ -r /etc/dconf/profile/amerika ] && export DCONF_PROFILE=amerika
[ -r "$share/fonts.conf" ] && export FONTCONFIG_FILE="$share/fonts.conf"

# Qt applications read colours, fonts and icons from kdeglobals (written by amerika-first-run) via plasma-integration.
for plugin in /usr/lib/*/qt6/plugins/platformthemes/KDEPlatformTheme.so; do
  [ -e "$plugin" ] && { export QT_QPA_PLATFORMTHEME=kde; break; }
done

# Electron/Chromium: use Wayland when available; colour scheme comes from the Settings portal.
export ELECTRON_OZONE_PLATFORM_HINT=auto

# Cursor for X11/XWayland clients and toolkits that ignore the settings above.
export XCURSOR_THEME="${XCURSOR_THEME:-breeze_cursors}"
export XCURSOR_SIZE="${XCURSOR_SIZE:-24}"
unset share plugin
