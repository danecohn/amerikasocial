---
name: hardware-surface-laptop-7
description: What the Surface Laptop 7 (Snapdragon X, Adreno X1-85, Hexagon NPU) can and cannot do under AltStack Desktop - Vulkan on the turnip driver, performance modes, thermals, memory, NPU reality, x86 emulation. Use for performance, battery, thermal, GPU, game-speed or "can the NPU do X" questions.
---

# Hardware: Surface Laptop 7 (Snapdragon X)

Facts from the Amerika hardware tools (`amerika-gamedev`): 12-core Qualcomm Oryon CPU, Adreno X1-85 GPU with the kernel `msm` driver and Mesa **turnip** (Vulkan 1.4) / freedreno (OpenGL), about 16 GB RAM, Hexagon NPU/DSP. Always check the live machine with `amerika.hw.report` (CPU governor and max MHz, memory, swap/zram, Vulkan device and driver, GPU clocks, thermals, NPU, tools, advice) - do not answer from this file when the report is available.

## Procedures
**"Why is it slow/hot?"** `amerika.hw.report` + `amerika.system.status` (power profile, battery). Look at: available memory and swap, thermal readings, governor. Then act: close or ask about heavy windows; `amerika.power.set_profile {profile:"balanced"}`.
**"Make the game/build faster":**
1. `amerika.power.set_profile {profile:"performance"}` (act; tell the user battery and heat cost; keep the charger in).
2. `amerika.hw.perf {mode:"game"}` pins CPU and GPU clocks high until reboot. It is **critical** and shows an administrator prompt (pkexec): ask the user first, explain, wait for the dialog. When done: `amerika.hw.perf {mode:"balanced"}` and `amerika.power.set_profile {profile:"balanced"}`.
3. Use the Vulkan renderer in Godot (the GPU is the real lever). Studio launchers already start under `gamemoderun` when installed.
4. Verify with `amerika.hw.report` again (GPU clocks) and report numbers actually read.
**"Tune the system"** (zram swap, bigger file-watch/mmap limits, shader cache): `amerika-hw tune apply` is opt-in and needs the user at a terminal; revert with `amerika-hw tune revert`. Describe it; do not run it for them.
**Benchmarks:** `amerika-hw bench` (vkmark/glmark2) must run on the desktop; ask the user, then it needs a shell command they approve.

## What it can / cannot do
- **GPU:** Mesa's driver, not replaceable. Good for Vulkan 1.4 games and Godot/Blender viewport work. `perf game` removes clock ramp-up delay; it does not add power.
- **NPU:** runs neural-network inference only. It cannot accelerate rendering or frame rates. `/dev/fastrpc-cdsp` exists, but Qualcomm's user-space runtime and signed DSP libraries are not packaged for Ubuntu, so nothing runs on it today. Say this plainly if asked; do not suggest it for games, builds or local models. (`amerika-hw npu` reports the same.)
- **x86_64 programs:** only through `box64` (emulation, large slowdown). Native arm64 builds are the goal.
- **Thermals:** thin chassis; sustained load will throttle. Suggest breaks, power, hard surface. The report shows temperatures; quote them.
- **Battery:** `amerika.system.status` shows charge and state. Charge-limit settings are in Settings > Power.
- **Unverified on the real laptop here:** lock screen, suspend/resume, docking and recovery. Do not promise them.

## Rules
- Anything that changes clocks, governors or kernel settings needs the user's yes first; always offer the revert.
- Do not edit `/sys` or `/etc` files yourself, and do not run `sudo`.
- If `amerika.hw.report` fails with "not installed", the user lacks `amerika-gamedev`: say so, and use `amerika.system.status` and `amerika.system.info` instead.

## Failure handling
- pkexec dialog cancelled: report "mode unchanged"; confirm with `amerika.hw.report`.
- Temperatures missing: sensors not exposed; say unknown instead of guessing.
