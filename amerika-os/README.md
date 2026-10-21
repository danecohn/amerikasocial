# Amerika OS

Amerika OS is a desktop environment built on KDE Plasma and KWin (Wayland), with a macOS-inspired
retro-futurist look: a top menu bar, a floating dock that never hides, dark chrome-and-crimson styling,
and a signed APT repository hosted by Amerika Social at <https://www.amerika.social/apt>.

It is **not** a new Linux distribution or kernel. The shell package links to the stock Plasma views, so it
receives upstream fixes; Amerika adds the panels, session, theme, apps and software manager.

## Install (Ubuntu 26.10, ARM64)

See <https://www.amerika.social/downloads/os>. In short: add the signing key and the `amerika.sources` file, then
`sudo apt install amerika-desktop` and choose **Amerika OS** on the login screen. The Plasma session stays available.

Signing key fingerprint: `9F52 BD98 A8EE 9096 B1BE 7AAC 1063 BBC9 89A1 1133`

## Packages

| Package | Contents |
| --- | --- |
| `amerika-desktop` | Meta package that installs everything below |
| `amerika-session` | Login session entry, `amerika-session`, first-run theming (Amerika session only) |
| `amerika-desktop-shell` | `org.amerika.shell` plasmashell package: top bar and floating dock layout |
| `amerika-theme`, `amerika-icon-theme` | Color scheme, wallpaper, Konsole profile, look-and-feel, icons |
| `amerika-hub` | Start screen (PyQt6) |
| `amerika-apps` | Files, Terminal, Text, Settings, AI launchers (branded launchers for Dolphin, Konsole, Kate, System Settings) |
| `amerika-software` | Graphical package manager and its Polkit-guarded root helper |
| `amerika-social`, `amerika-venture`, `amerika-office` | Application payloads repackaged from the published ARM64 releases |
| `amerika-repo-keyring` | Signing key and `/etc/apt/sources.list.d/amerika.sources` |

Only ARM64 is built and tested. x86-64 is not advertised.

## How the session works

`/usr/share/wayland-sessions/amerika.desktop` runs `amerika-session`, which sets `AMERIKA_SESSION=1` and starts
`startplasma-wayland`. `/etc/xdg/plasma-workspace/env/50-amerika-session.sh` (sourced by startplasma) then exports
`PLASMA_DEFAULT_SHELL=org.amerika.shell` for that session only. The regular Plasma session never sets the variable.
The shell package contains its own `layout.js` (top bar and dock) and symlinks to the stock Plasma shell views.

## Amerika Software

`amerika-software` lists packages whose candidate comes from the trusted `Amerika` origin at `www.amerika.social`
(via python-apt). Changes run `pkexec /usr/libexec/amerika-software-helper <action> [packages]`. The helper
only accepts `update`, `install`, `remove` and `upgrade`, validates names (`^[a-z0-9][a-z0-9+.-]+$`) and
membership in the verified Amerika catalog, never uses a shell, and passes `--` before package names.

## Build

```bash
python3 build.py --init-key          # once; key goes to ~/.local/share/amerika-os-signing (never in git)
python3 build.py                     # builds ./dist/packages and the signed ./dist/apt tree
python3 tools/stage-for-social.py ../path/to/amerikasocial   # copies metadata + small debs into apt-repo/
python3 -m unittest discover tests   # helper validation tests
tools/nested-shell-test.sh           # headless KWin on a private D-Bus; needs dbus-run-session
```

The application payloads come from the verified release archives (SHA-256 checked in `build.py`).
Packages over 20 MB (Social, Venture, Office) are not committed. They are attached to the GitHub release
`os-1.0.0` of `danecohn/amerikasocial`; Social redirects pool requests for exactly those file names to that
release, and APT verifies size and SHA-256 against the signed `Packages` index.

## Key handling

The private signing key lives only in `$AMERIKA_SIGNING_HOME` (default `~/.local/share/amerika-os-signing`),
is not in this repository and must be backed up by the owner. The public key is in `apt-repo/` and in
`amerika-repo-keyring`. Rotating it means shipping a new keyring package signed by the old key first.

## Limitations

* The Amerika session was verified in an isolated headless KWin and package-by-package, not through a full
  login-manager login on a fresh machine.
* Window decorations are Breeze, not a custom macOS-style decoration.
* The Social, Venture and Office packages ship unsigned upstream builds (see their copyright files).
* Venture is Mozilla Firefox 158.0.1 with Amerika branding, not a full rebuild. Office keeps ONLYOFFICE
  Community Edition branding. Upstream licenses are preserved in each package.

License: GPL-3.0-only for Amerika code. Third-party components keep their own licenses.
