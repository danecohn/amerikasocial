---
name: software-and-updates
description: Install, update or remove software on AltStack Desktop - Amerika Software (the amerika-software helper), apt, update channels (stable/testing) and what needs approval. Use when the user asks to install an app or package, check for updates, upgrade, or switch the update channel.
---

# Software and updates

**There is no software-install tool.** Package changes need administrator rights and always go through a polkit prompt that only the user can answer. You prepare, explain and verify; the user authorises.

## Where software comes from
- **Amerika packages** (`amerika-*`, signed repository www.amerika.social): install and update with the **Amerika Software** app (`amerika.apps.launch {id: "amerika-software"}`). It uses a fixed helper (`amerika-software-helper`) that only accepts packages listed in the verified Amerika index; the user sees a polkit dialog.
- **Ubuntu packages and updates:** Settings > Updates (`amerika-settings updates`) does "refresh" and a no-removal upgrade through a fixed helper. Open it with `amerika.apps.launch {id: "amerika-settings"}` and tell the user the page.
- **Channels:** `stable` (default) or `testing` (opt-in; testing packages install only on explicit request). `amerika-channel status` is read-only; `amerika-channel stable|testing` needs root and changes only the Amerika testing source file. Never change the channel unless the user clearly asks, and never suggest disabling signature verification or `trusted=yes`.

## Read-only checks (no admin rights)
Use `amerika.shell.run` (critical: the user approves each command; show it verbatim) with one of these, never chained:
- `apt list --upgradable 2>/dev/null` - what could be updated.
- `apt-cache policy PACKAGE` - versions and origins.
- `dpkg -l 'amerika-*'` - installed Amerika packages and versions.
- `amerika-channel status` - stable or testing.
- `cat /etc/amerika-os/channel` - same, from the state file.
Also `amerika.system.info` for OS and kernel.

## Procedures
**"Install X":** 1) `apt-cache policy X` via shell.run to confirm it exists and where from (if the user did not name a package exactly, ask). 2) For an Amerika package, open Amerika Software and tell the user: search X, press Install, approve the polkit prompt. 3) For Ubuntu, tell them the exact command to run in a terminal (`sudo apt install X`) or, if they ask you to run it, say that sudo/pkexec cannot be answered by you; they run it. 4) Afterwards verify with `dpkg -l X`.
**"Update everything":** open Settings > Updates; let the user press refresh and upgrade. Report what `apt list --upgradable` showed before. Never run `dist-upgrade`/`full-upgrade`, never remove packages, never run a display-manager upgrade while a session is open (the helper defers it; say so).
**Kernel or firmware updates:** warn that a reboot is needed (`/var/run/reboot-required`), and that this laptop's recovery paths are not fully tested; ask the user to save work first. Do not reboot (`amerika.power.reboot` asks, but also ask yourself: is it wanted now?).
**"Switch to testing/stable":** explain the effect in two sentences, then ask for a clear yes; give them `sudo amerika-channel testing` followed by `sudo apt update`.

## Rules
- Never run `sudo`, `pkexec`, `apt install/remove/purge`, `dpkg -i`, `pip install --break-system-packages`, `curl | sh` or add repositories/keys via `amerika.shell.run`.
- Do not download and run installers from the web. Ubuntu/Amerika repositories first; if the user insists on something else, explain the risk and let them do it.
- Never edit `/etc/apt` files. Keep the Amerika repo keyring package.
- Report versions you actually read, not what you expect.

## Failure handling
- "not in the Amerika repository": it is not an Amerika package; try Ubuntu.
- Polkit dialog never appears (no agent running): tell the user to run the command in a terminal.
- Update fails: `amerika.journal.read` is for user units only; ask the user for the terminal output or run `apt-get -s upgrade` (simulation) via shell.run.
