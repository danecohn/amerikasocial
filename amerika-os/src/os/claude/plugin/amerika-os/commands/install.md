---
description: "Install software (you approve the administrator prompt)"
argument-hint: "package or app name"
---

Wanted: $ARGUMENTS. You cannot install anything yourself. Check where it comes from with `amerika.shell.run` (approved): `apt-cache policy NAME`. For an Amerika package open `amerika.apps.launch {id: "amerika-software"}` and give the steps (search, Install, approve the polkit dialog). For an Ubuntu package give the exact terminal command `sudo apt install NAME`. Never run sudo, pkexec or apt install, never add repositories. After the user says it is done, verify with `dpkg -l NAME` and report the version read.

Rules: follow the software-and-updates skill. Verify the result with a read tool and report only what you verified. If a tool fails or the user declines, say so and stop; do not retry or look for another way around the refusal.
