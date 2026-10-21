# Development verification

Use Ubuntu 26.10 ARM64 with GTK4, KWin, a C compiler, the Python shared library, WebKitGTK 6 and the pinned Node 24 engine.
The test laptop is ARM64; no x86-64 or physical hardware behaviour is implied by a headless pass.

```
python3 -m unittest discover -s tests -q
sh tests/rig/agent-rig.sh 'sh tests/rig/agent_settings_test.sh'
sh tests/rig/agent-rig.sh 'sh tests/rig/settings_pages_test.sh'
sh tools/kwin-rig.sh 'sh tests/rig/agent_gateway.sh'
AMERIKA_SHELL_HOST="$PWD/dist/native/amerika-shell-host" sh tests/rig/desktop_rig.sh 'sh tests/rig/desktop_services_test.sh'
python3 tools/build-iso.py --dry-run
```

All three compositor runners create private D-Bus, HOME, XDG configuration/state/data/cache **and runtime** directories.
Never substitute the live runtime directory: a second broker could otherwise replace its control socket.
Cleanup uses exact child PIDs. Rigs must propagate the test program's exit status.

Agent Settings uses a fake CLI and only obvious `sk-test-FAKE` values. The gateway rig uses the published pinned engine,
actual shell MCP broker, fake secret-tool and one-time ephemeral browser pairing. The desktop rig runs the native host,
creates real virtual-compositor windows/desktops, checks selection/filter/activation, captures actual pixels, changes and
restores the virtual scale, and saves an actual WebM from compositor frames. It does not adjust the real laptop's volume,
brightness, networking, password, boot, display manager or disks.

Settings screenshot fixtures replace system commands before controls are built. All 23 pages must load without an error
card. Fixture screenshots establish UI rendering and data mapping, not that every hardware backend works on the laptop.

A release needs physical keyboard/Alt-release, touchscreen/pen, clipboard password hints, audio routes/Bluetooth pairing,
Wi-Fi/VPN, docking/scaling, lock/resume and recovery checks. A bootable, installable ARM64 ISO needs separate VM and Surface
boot/installer/Secure Boot verification. The current ISO helper is a dry-run/preparation tool; it never executes a privileged build.
