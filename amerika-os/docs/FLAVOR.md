# Amerika Ubuntu flavour development

AltStack Desktop is an independent desktop built on **Ubuntu 26.10 ARM64**, using KWin as compositor and its own GTK shell.
It is not an officially recognised Ubuntu flavour. `/etc/os-release` remains Ubuntu's; desktop identity is in
`/usr/share/amerika-os/flavour`. No x86-64, Surface ISO, Secure Boot or completed installer support is asserted.

The builders provide `amerika-standard`, `amerika-desktop-minimal`, `amerika-desktop`, `amerika-desktop-full`, branding,
application defaults, manuals and signed stable/testing channel configuration. Seeds under `flavor/seeds` are the
source for the new metapackages. Minimal excludes the large Social/Venture/Office wrappers. Full adds optional apps as
Recommends so individual applications can be removed. The normal desktop includes the OpenClaw-backed Agent package,
whose gateway stays opt-in even when the package is installed.

Session defaults use a separate dconf profile and desktop-specific portal configuration. Existing user preferences
win. MIME defaults are desktop-scoped; fonts are selected by the Amerika session environment. KDE's portal backend
provides compatible capture/screencast services; this is not a new independently implemented Amerika portal backend.
The GTK backend supplies pickers. Do not claim every portal works until tested with real applications on hardware.

GRUB artwork is installed as data only. Packages never select it, run grub-install or replace a bootloader. Login and
Plymouth helpers retain their explicit enable/disable model. A live installer that makes different defaults needs its
own reviewed, reversible configuration and physical recovery tests.

## Repository and ISO preparation

Stable local packages remain in `dist/apt`. Development versions build into `dist/development/apt`, with the same known
archive signing identity. Both contain signed APT metadata; a development version is not a stable release. The hosted
repository and Railway deployment remain unchanged while deployments are paused.

`python3 tools/build-iso.py --dry-run --repo dist/development/apt` prints the ARM64 live-build plan without root, network,
package installation or disk writes. `--prepare --output /a/new/empty/build-directory` writes an inspectable workspace.
That workspace uses a signed snapshot served from the disposable build VM's localhost. It does not run live-build.
The plan currently creates a **live desktop only, without an installer**. Calamares, encrypted installation, partitions,
Snapdragon kernel/firmware selection, Secure Boot and first-boot defaults remain explicit release gates. The generic
ARM64 kernel in the plan is not evidence of Surface support. Do not present the plan as a boot-tested ISO.

## Packaging

`python3 build.py --only PACKAGE,... --no-repo` builds selected packages without accessing signing material.
Repository generation is separate and requires the existing local archive key. An absent signing key is an error;
normal builds no longer silently create a replacement. `flavor/keys` contains public archive material only.
A source packaging skeleton and CI templates are provided for review; they need a clean Ubuntu build/CI run before a
release can claim Debian policy or lintian compliance. OpenClaw is a separately pinned npm bundle, not vendored source.
