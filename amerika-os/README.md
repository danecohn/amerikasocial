# Amerika OS

Amerika OS is a desktop environment built on the **COSMIC** desktop (System76) with a macOS-inspired
retro-futurist look: a top menu bar, a floating dock that never hides, a dark chrome-and-crimson theme, and a
signed APT repository hosted by Amerika Social at <https://www.amerika.social/apt>.

It is **not** a new Linux distribution or kernel. Amerika adds a session, panel and dock layout, theme, apps and a
software manager on top of COSMIC. Version 1.x was built on KDE Plasma; that variant is still available as the
`amerika-plasma` package.

## Install (Ubuntu 26.10, ARM64)

See <https://www.amerika.social/downloads/os>, or run `outputs/Install-Amerika-OS.sh`. In short: add the signing key and the
`amerika.sources` file, then `sudo apt install amerika-desktop` and choose **Amerika OS** on the login screen.
Your login manager and existing sessions are left as they are.

Amerika signing key fingerprint: `9F52 BD98 A8EE 9096 B1BE 7AAC 1063 BBC9 89A1 1133`

## Packages

| Package | Contents |
| --- | --- |
| `amerika-desktop` | Meta package that installs everything below plus the COSMIC session |
| `amerika-session` | Login session entry, `amerika-session`, one-time seeding of the Amerika layout and theme |
| `amerika-desktop-shell` | Seed files for the Amerika top bar, dock, dock favorites and wallpaper setting |
| `amerika-theme`, `amerika-icon-theme` | COSMIC dark theme with crimson accents, horizon wallpaper, AmerikaOS icons |
| `amerika-hub` | Start screen (PyQt6) |
| `amerika-apps` | Files, Terminal, Text, Settings, AI launchers (branded launchers for COSMIC Files, Terminal, Edit, Settings) |
| `amerika-software` | Graphical package manager and its Polkit-guarded root helper |
| `amerika-social`, `amerika-venture`, `amerika-office` | Application payloads repackaged from the published ARM64 releases |
| `amerika-repo-keyring` | Amerika signing key and `/etc/apt/sources.list.d/amerika.sources` |
| `amerika-plasma` | Legacy Amerika OS on KDE Plasma (session, shell package, KDE theme); not part of `amerika-desktop` |
| 34 COSMIC packages | `cosmic-*`, `pop-launcher`, `pop-fonts`, `xdg-desktop-portal-cosmic` and friends, mirrored unmodified |

Only ARM64 is built and tested. x86-64 is not advertised.

## COSMIC packages

Ubuntu 26.10 does not ship COSMIC, and its APT (sqv) rejects the Pop!_OS archive key because the key's
self-signature uses SHA-1, so the Pop!_OS repository cannot be added as an APT source. `tools/fetch-cosmic.py`
therefore verifies it manually: GnuPG must validate `InRelease` against the pinned System76 key
(`63C4 6DF0 140D 7389 6142 9F4E 204D D8AE C33A 7AFF`, also named in pop-os/iso), the Packages index must match the
signed hash, and every `.deb` must match the index. The unmodified files are stored in `vendor/cosmic` with a
manifest (including each package's upstream commit, taken from the version suffix) and re-hosted by Amerika.
The packages are built by System76 for Ubuntu 26.04; their dependencies were checked with `apt-get -s` on 26.10.
COSMIC is GPL-3.0; the source is at <https://github.com/pop-os/cosmic-epoch> and the component repositories.
COSMIC updates reach users when Amerika re-runs `fetch-cosmic.py` and publishes a new repository version.

## How the session works

`/usr/share/wayland-sessions/amerika.desktop` runs `amerika-session`, which sets `AMERIKA_SESSION=1`, runs
`amerika-cosmic-seed` and then `start-cosmic`. The seeder copies `/usr/share/amerika-os/cosmic/*` (COSMIC
configuration files: panel, dock, app list favorites, background, dark theme, icon theme) into
`~/.config/cosmic` once (marker `~/.local/state/amerika-os/cosmic-seed-2`). The files are derived at build time from
the stock COSMIC defaults, so key names and formats match the shipped COSMIC version.

## Amerika Software

`amerika-software` lists packages whose candidate comes from the trusted `Amerika` origin at `www.amerika.social`
(via python-apt). Changes run `pkexec /usr/libexec/amerika-software-helper <action> [packages]`. The helper
only accepts `update`, `install`, `remove` and `upgrade`, validates names and membership in the verified Amerika
catalog, never uses a shell, and passes `--` before package names. It also keeps the current default login manager
when a package such as `cosmic-greeter` is installed or upgraded.

## Build

```bash
python3 tools/fetch-cosmic.py        # verifies and downloads the COSMIC packages into vendor/cosmic
python3 build.py --init-key          # once; key goes to ~/.local/share/amerika-os-signing (never in git)
python3 build.py                     # builds ./dist/packages and the signed ./dist/apt tree
python3 tools/stage-for-social.py ../path/to/amerikasocial   # copies metadata + small debs into apt-repo/
python3 -m unittest discover tests   # helper validation tests
tools/nested-cosmic-test.sh          # COSMIC layout nested in the current session on a private D-Bus
```

The application payloads come from the verified release archives (SHA-256 checked in `build.py`). Packages over
5 MB (apps and COSMIC) are not committed. They are attached to GitHub releases of `danecohn/amerikasocial`; Social
redirects pool requests for exactly those file names, and APT verifies size and SHA-256 against the signed index.

## Key handling

The private signing key lives only in `$AMERIKA_SIGNING_HOME` (default `~/.local/share/amerika-os-signing`), is not in
this repository and must be backed up by the owner. Rotating it means shipping a new keyring package signed by the
old key first.

## Limitations

* The COSMIC layout was verified in a nested COSMIC compositor (panel and dock components start from the seeded
  configuration) and package-by-package, not through a real login-manager login on a fresh machine.
* The Amerika theme recolours COSMIC's stock Dark theme files; opening COSMIC Settings > Appearance may regenerate
  colours from the theme builder values.
* Window decorations are COSMIC's own, not a custom macOS-style set.
* COSMIC packages are System76's builds for Ubuntu 26.04 used on 26.10.
* The Social, Venture and Office packages ship unsigned upstream builds (see their copyright files).
* Venture is Mozilla Firefox 158.0.1 with Amerika branding, not a full rebuild. Office keeps ONLYOFFICE Community
  Edition branding. Upstream licenses are preserved in each package.

License: GPL-3.0-only for Amerika code. Third-party components keep their own licenses.
