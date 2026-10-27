---
name: system-settings
description: Read and change AltStack Desktop settings safely - appearance, sound, brightness, display scale, Wi-Fi, power profile, Copilot key, top bar, home mode - one page at a time, with a way back. Use when the user asks to change how the computer looks, sounds or behaves.
---

# System settings

## Two kinds of settings
1. **Direct tools** for live system state: `amerika.audio.set_volume {percent 0-150}`, `amerika.audio.set_mute {muted}`, `amerika.display.set_brightness {percent 1-100}`, `amerika.display.set_scale {output, scale 0.5-4}`, `amerika.network.set_wifi {on}`, `amerika.power.set_profile {profile: power-saver|balanced|performance}`.
2. **Amerika preferences** through `amerika.settings.get` / `amerika.settings.set {key, value}`. Writable keys are exactly what the tool's schema lists (currently `accent`, `secondary` as `#rrggbb`, `wallpaper` horizon|grid|dusk, `dock_size` 32-96, `clock_24h`, `copilot_app` caster|claude|chatgpt|agent|ask, `home_mode` claude|chatgpt|off, `dock_enabled`, `bar_height` 28-64, and any key the settings API adds later). The top bar has its own tools: `amerika.bar.get` / `amerika.bar.set`; text size is `amerika.ui.text_scale`; the whole style is `amerika.ui.mode`.

Anything else (network details, Bluetooth pairing, users, privacy, updates, login) is not a tool: open the page for the user with `amerika.ui.settings {page}` and tell them what to do there (`amerika-settings display`, `network`, `sound`, `power`, `appearance`, `notifications`, `privacy`, `updates`, `login`, `ai`, `agent`, `studio` ...). Do not edit settings files by hand.

## Procedure
1. **Read before write:** `amerika.settings.get` (preferences) or `amerika.system.status` (battery, network, volume, brightness, power profile, displays). Remember the old value.
2. **Change one thing.** Use the exact key and a value inside the allowed range. The shell validates; an error text tells you the rule.
3. **Read back.** Confirm the new value from the same read tool. For visual changes (accent, scale, bar) say what the user should now see.
4. **Offer the revert:** state the old value ("accent was #ff2e63; say the word and I restore it").

## Per page notes
- **Appearance:** accent and secondary colours must be `#` plus six hex digits. Ask which colours if the user says only "make it blue"; propose a value, then apply.
- **Display:** scale changes can make text unreadable or windows overflow. Use `amerika.system.status` to get the output name. Change by at most 0.25 at a time and confirm with the user; the Settings app has a revert timer, tools do not.
- **Sound / brightness:** values above 100 volume can distort; ask before going over 100.
- **Wi-Fi off** cuts the connection Claude may be using. Ask before turning it off, and never do it in the middle of another task that needs the network.
- **Power profile:** `performance` costs battery and heat; `power-saver` slows builds. See `amerika-hardware-surface-laptop-7`.
- **Copilot key:** `copilot_app` takes caster (the Claude/ChatGPT switcher), claude, chatgpt, agent or ask.
- **Home mode / dock:** `home_mode` and `dock_enabled` are settings keys; prefer `amerika.ui.mode` to move between Claude-first and Classic. Text scale: `amerika.ui.text_scale`.

## Safety
- Never change AI permission settings (`ai` mode, grants, enabled clients) - not tool-reachable by design, and you must not try via files or shell.
- Do not batch many changes without telling the user the list first.
- Revert immediately if the user says it looks wrong; do not argue.

## Failure handling
- "This setting is not writable through the settings API": it is not a tool setting; use the Settings app page.
- Value rejected: show the rule from the error, offer a valid value.
- Read-back differs from what you set: report the difference; do not retry in a loop (once is enough).
