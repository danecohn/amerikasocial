---
name: diagnose-and-repair
description: Diagnose and repair problems on Amerika OS - something is slow, broken, missing or will not start. Reads the user journal, hardware report, units and status first, applies the safest fix, and knows the recovery paths for the login, boot and session screens. Use when the user reports an error, crash, black screen, lag, no sound/Wi-Fi, or a service that does not work.
---

# Diagnose and repair

Order: **observe -> explain -> propose -> fix the smallest thing -> verify.** Never start with a reboot or a reinstall.

## 1. Observe (all read-only, no approval)
- `amerika.system.status`: battery, network, volume, brightness, power profile, displays.
- `amerika.system.info`: OS, kernel, uptime.
- `amerika.windows.list`: is the app running? is a window off-screen or minimized?
- `amerika.units.status` (no args lists all `amerika-*` user units; with `{unit: "amerika-studio-bridge"}` shows one: ActiveState, SubState, NRestarts).
- `amerika.journal.read {lines: 100, priority: "err"}`; add `{unit: "amerika-agent-gateway.service"}` or `{since: "30 minutes ago"}`. Output is capped and secrets are redacted; if something still looks like a key, do not quote it.
- `amerika.hw.report`: CPU, memory/swap/zram, Vulkan driver, GPU clocks, thermals, NPU, advice (needs `amerika-gamedev`; if "not installed", skip).
- `amerika.agent.status`, `amerika.studio.status`: optional components.
- `amerika.notifications.list`: recent error toasts.

## 2. Common cases
| Symptom | Check | Safe fix |
|---|---|---|
| Slow / hot | `hw.report` (thermals, available_mb, swap), `system.status` power profile | close heavy windows (ask), `power.set_profile balanced`; for games see `amerika-hardware-surface-laptop-7` |
| No sound | `system.status` volume/mute | `audio.set_mute {muted:false}`, `audio.set_volume` |
| No network | `system.status` network | `network.set_wifi {on:true}`; open Settings > Network for the rest |
| Studio app fails | `studio.status`, `units.status {unit:"amerika-studio-bridge"}`, journal for that unit | `units.restart {unit:"amerika-studio-bridge.service"}` (asks) |
| Agent not answering | `agent.status`, journal unit `amerika-agent-gateway.service` | `units.restart` that unit; else tell the user to open Settings > Agent |
| App window missing | `windows.list` | `windows.restore`/`windows.focus`/`windows.to_desktop`/`windows.move_resize` |
| Shell/bar frozen | tools time out | do not restart the shell yourself (not allowed); give the user the recovery steps below |

## 3. Restart rules
`amerika.units.restart` only accepts `amerika-*.service` user units, and refuses the shell, session, login and broker units, because restarting them would cut your own connection. Restart once, wait a few seconds, check `units.status`, read the journal again. If it fails twice, stop and report.

## 4. Recovery paths (give these to the user; you cannot run them)
- Broken Amerika session: Ctrl+Alt+F3 (a text console), log in, then `amerika-agent disable --now`; `amerika-login disable` and/or `amerika-boot disable` if the Amerika login/boot themes were enabled; choose the fallback desktop (Plasma) at the login screen.
- Login screen themed and broken: the fallback unit `amerika-login-fallback.service` exists for this; `amerika-login status` shows state.
- Boot theme problem: `amerika-boot status`, `amerika-boot disable`.
- Hardware tuning: `amerika-hw tune revert` and `amerika-hw perf balanced` undo everything.
- Save logs locally before sharing; review and redact private content. Lock screen, sleep/resume and the recovery paths are not fully tested on the real laptop: say so, do not promise.

## 5. Rules
- State the likely cause as a hypothesis with the evidence ("the journal shows X at 10:42"). Do not present a guess as a diagnosis.
- Fix with the least invasive action first; undoing must be possible. Ask before anything `sensitive` or `critical`.
- `amerika.shell.run` for diagnosis only when no read tool covers it (for example `df -h ~`, `free -h`, `systemctl --user --failed`); one command per call, read-only, no `sudo`.
- Never delete caches, configs or `~/.config` entries as a "fix" without the user's yes and a backup.
- After any fix, re-run the observation that showed the problem and report the before/after. If it is not fixed, say that.

## Failure handling
- Journal empty: the unit may not log to the user journal; try without `unit`, widen `since`.
- "systemctl not available" / "journalctl" errors: running outside a user session; tell the user.
