---
description: "Remove software (you approve; asks every time)"
argument-hint: "package or app name"
---

Target: $ARGUMENTS. Find the installed package and what depends on it with `amerika.shell.run` (approved, read-only): `dpkg -l NAME` and `apt-cache rdepends --installed NAME`. Explain what will go and what data stays. Never remove amerika-* core packages (the shell, session, repo keyring) yourself or advise it without a warning. The removal is done by the user: Amerika Software for Amerika packages, otherwise `sudo apt remove NAME` in a terminal. Verify afterwards with `dpkg -l NAME`.

Rules: follow the software-and-updates skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
