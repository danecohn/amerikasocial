# Amerika OS welcome / first-run spec

`welcome.json` describes the pages and actions of the welcome window that follows the one-time look-and-feel setup of
`amerika-first-run` (`src/os/amerika/firstrun.py`, owned by the shell team and **not** edited here). The shell UI can load
it from `/usr/share/amerika-os/welcome/welcome.json` (installed by `amerika-branding`).

Rules for consumers:

* `steps[].actions[].type` is one of `next`, `finish`, `command`, `settings-page`, `app`, `link`.
* `command` actions run `argv` directly (no shell). If `privileged` is true, run through `pkexec` after showing `confirm`.
* Show-once state: store `show_once_key` under `~/.local/state/amerika-os/` (same directory as the `first-run` marker).
* Skip everything when `$AMERIKA_LIVE` is set (the live session) or when the marker exists.
* Every command is an existing, documented CLI (`man amerika-login`, `man amerika-boot`, `man amerika-channel`).

`welcome.schema.json` is a JSON Schema for validation (used by `tests/test_flavor.py`).
