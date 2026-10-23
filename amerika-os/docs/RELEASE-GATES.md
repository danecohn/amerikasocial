# Gates before AltStack Desktop 3.1.0

3.1.0 is built as a local release candidate. The remaining gates below still need the owner's laptop, own API key, hardware and a
VM install; do not describe them as verified, and do not change the production deployment based on unit/headless tests alone.
Completed since the first draft: KWin's own compositor-enforced screen lock (kscreenlocker via `loginctl lock-session`; the virtual
KWin reports the lock active; the real authentication prompt still needs the owner's check) and an `apt-get -s install amerika-desktop`
resolution against the Ubuntu 26.10 archive plus the signed Amerika repo.

Completed local evidence includes pinned-engine configuration/MCP/loopback/browser pairing, fake-key secret handling,
GTK Agent onboarding, all 23 Settings page renders, virtual desktops/window picker/overview/clipboard/calendar/OSD,
real KWin pixel capture, virtual scale rollback and a real compositor WebM. See DEVELOPMENT-TESTING.md for exact tests.

Required remaining evidence/work:

- Real Anthropic/OpenAI model request, tool approvals and cancellation, performed by the user with their own key in
  native Settings; keyring unlock/relock and actual systemd login/logout lifecycle.
- Physical keyboard Alt release, Surface touch/pen, Bluetooth PIN pairing, Wi-Fi variants/VPN/hotspot, audio routing,
  per-app streams, brightness, battery charge support, docking, multiple outputs, scaling/rotation/HDR.
- A reviewed compositor-enforced lock with actual authentication, idle/suspend/resume and recovery. A GTK overlay is insufficient.
- A complete installer and bootable ARM64 image, clean VM install, Surface boot/kernel/firmware, Secure Boot and recovery.
- Portal sharing in real browsers/OBS/calls, notification edge cases/inline replies, accessibility service integration,
  robust gesture and session-restore behaviour. Search/window rules/power management need further parity checks.
- Clean Debian source build, lintian and CI run; dependency-install simulation against the intended Ubuntu archive;
  reproducible package comparison and a complete corresponding-source/licence review of bundled dependencies.
- Explicit owner instruction before GitHub push/release asset upload; explicit end of the Railway pause before deployment.

The existing stable local installer/repository stays available. A development test requires an explicit choice and a
fallback session; it must not quietly replace the stable installation path.
