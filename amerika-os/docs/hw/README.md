# Amerika Game Dev Tools (Surface Laptop 7 / Snapdragon X)

Tailored to this machine: 12-core Qualcomm Oryon CPU, Adreno X1-85 GPU (kernel `msm` + Mesa **turnip** Vulkan 1.4 / freedreno GL), ~16 GB RAM, Hexagon NPU/DSP.

```
amerika-hw                 # report: CPU, RAM/swap/zram, Vulkan device + driver, GPU clocks, thermals, NPU status, tools, advice
amerika-hw perf game       # CPU + GPU clocks pinned high while you work (runtime only; resets on reboot)
amerika-hw perf balanced   # put them back
amerika-hw tune apply      # opt-in: zram swap, larger file-watch/mmap limits, big shader cache (revert: amerika-hw tune revert)
amerika-hw bench           # vkmark / glmark2 scores (run on the desktop)
amerika-hw npu             # what the NPU can and cannot do here
```

## What is and isn't possible with the NPU and GPU
- **GPU:** the real graphics lever. The Adreno driver is Mesa's; we do not replace it. `perf game` removes clock ramp-up latency; the shader cache setting avoids shader recompiles; Godot should use the Vulkan renderer.
- **NPU:** it runs neural-network inference, not rendering, so it cannot boost frame rates. The kernel exposes `/dev/fastrpc-cdsp`, but Qualcomm's user-space runtime and signed DSP libraries are not packaged for Ubuntu, so nothing can run on it yet. `amerika-hw npu` reports this honestly. If a runtime appears, Amerika Agent can use it as a local-model backend.
- **x86_64 games/tools:** `box64` (Recommends) runs x86_64 Linux binaries for testing builds; it is user-space emulation, expect a large slowdown.

## Applied by default by the Studio launchers
`amerika-engine` and `amerika-render` start under `gamemoderun` when it is installed (set `AMERIKA_NO_GAMEMODE=1` to disable).

## Undo
`amerika-hw tune revert`, `amerika-hw perf balanced`, or remove the package (it reverts both first).
