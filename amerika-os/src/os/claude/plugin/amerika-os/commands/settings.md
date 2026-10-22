---
description: "Open a Settings page or read a setting"
argument-hint: "page name | key"
allowed-tools: mcp__amerika__bar_get, mcp__plugin_amerika-os_amerika__bar_get, mcp__amerika__settings_get, mcp__plugin_amerika-os_amerika__settings_get
---

Request: $ARGUMENTS. If it names a page (network, bluetooth, sharing, display, sound, input, shortcuts, printers, power, appearance, notifications, accessibility, language, datetime, defaults, users, privacy, updates, storage, login, about, ai, agent, studio, home, topbar), call `amerika.ui.settings {page}` and tell the user what to look for there. If it names a setting, read it with `amerika.settings.get` or `amerika.bar.get`. With no argument, list the pages in one line each. Never write settings here.

Rules: follow the system-settings skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
