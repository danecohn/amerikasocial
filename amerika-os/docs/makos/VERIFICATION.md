# MakOS preview verification

MakOS 0.1.0 development preview is built for Ubuntu 26.10 ARM64. It is not a completed desktop.

The nine standalone logic/session tests passed. The earlier combined environment run passed 415 tests (one skipped).
The private KWin rig passed shell startup, real compositor pixels, native Qt window decoration, app navigation,
calculator results, unsaved editor protection, DBusMenu activation, notifications and frame callbacks. The extracted
Debian payload separately started Files and Settings in independent processes. This is rig evidence; the owner
has not confirmed a normal MakOS login. The detailed JSON records package hashes and image validation.

All 55 icons passed 1024x1024 RGBA, transparency, padding and alignment checks. Six original wallpapers are
shipped at 3840x2160 after resampling; the generation service returned smaller native images. The source JSON
records both dimensions. Material seam checks and cursor compilation passed. Four synthesized sound files exist;
sound playback policy remains unfinished.

Amerika Agent/OpenClaw is uninstalled (about 359 MB freed). ChatGPT, Claude and the Studio suite remain.
Duplicate app roles are absent from the MakOS catalog. Other system-wide app removal is pending a completed,
accepted MakOS session. Existing Plasma/Amerika fallbacks and user data are preserved.

## Try the preview

Extract `MakOS-0.1.0-dev.1-local-apt.tar.gz`, then run:

```sh
sh Install-MakOS-local.sh /absolute/path/to/extracted/apt
```

The installer verifies the established signing fingerprint and signed APT metadata before adding the six packages.
It does not select a session or change the login manager, boot theme or PAM. Log out normally and select MakOS
in the login screen. To return, log out and choose Plasma or Amerika OS. If the screen is blank, Ctrl+Alt+F3
opens a text login; inspect `~/.local/state/makos/shell.log`.

Uninstall the preview with:

```sh
sudo apt remove makos-desktop makos-apps makos-shell makos-session makos-theme makos-icons
sudo rm -f /etc/apt/sources.list.d/makos-local.sources /usr/share/keyrings/makos-archive-keyring.gpg
```

Keep the user's MakOS configuration and notes. Do not run autoremove as part of this procedure.

Open release gates include universal app menus, complete settings controls, SDDM/Plymouth opt-in integration,
full file-manager parity, gestures, remaining core apps, complete retained-engine skins, accessibility/hardware
acceptance and final software cleanup. See the repository README for scope.
