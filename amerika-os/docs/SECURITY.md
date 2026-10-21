# Security and recovery

This source is a development build, not a security-reviewed distribution. See THREAT-MODEL-AGENT.md for model/tool,
keyring, loopback, channel and owner-console boundaries. Tests use disposable HOME/XDG directories and fake secrets.
They do not authorize handling real credentials or modifying existing assistant configuration.

Privileged settings operations go through a fixed pkexec helper with a clean environment, isolated Python imports,
strict action/argument validation and no shell interpolation. It supports UFW, a 50–100% supported hardware charge limit,
APT refresh and a no-removal upgrade. Display-manager package upgrades are deferred, needrestart is list-only, and the
previous display-manager selection/unit is restored on failure. Normal Ubuntu package maintainer scripts may update
initramfs as part of a kernel upgrade; this is different from selecting an Amerika boot theme.

The helper never accepts caller-selected paths, package options or an environment-controlled system root. System
writes have fixture tests; they have not been exercised against this laptop's live firewall/battery/upgrade state.
Use the system terminal for deferred display-manager updates after saving work and leaving the desktop session.

Display previews are owned by a separate process. Reject, timeout or EOF from Settings restores the previous mode.
The private KWin rig verifies a real scale change and restoration after owner EOF. Physical displays, docking, HDR and
unplug/replug behaviour remain hardware checks. Forced termination of every process/power loss cannot guarantee rollback.

Login, boot and GRUB changes remain opt-in. Existing Plasma/other sessions are preserved. Recovery from a broken Amerika
session: use Ctrl+Alt+F3, sign in, stop the agent (`amerika-agent disable --now`), use `amerika-login disable` and/or
`amerika-boot disable` if you explicitly enabled those themes, then choose the fallback desktop at login. Save logs locally
and review/redact private content before sharing. No private archive signing key belongs in git, packages, an ISO or uploads.

Screen locking is not yet an independently reviewed Amerika implementation. Do not treat a decorative GTK window as a
security lock. Confirm a working compositor-enforced locker on the actual machine before relying on lock/idle/suspend policy.
