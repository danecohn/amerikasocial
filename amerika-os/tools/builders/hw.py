"""amerika-gamedev: Surface Laptop 7 / Snapdragon X game-development toolchain, hardware report and opt-in tuning."""
import shutil

TOOLCHAIN = ('build-essential, clang, lld, mold, cmake, ninja-build, ccache, pkgconf, git, git-lfs, gdb, lldb, libsdl3-dev, libvulkan-dev, '
             'libwayland-dev, libxkbcommon-dev, libopenal-dev, vulkan-tools, vulkan-validationlayers, spirv-tools, glslang-tools, mesa-utils, '
             'vkmark, glmark2-wayland, gamemode, lm-sensors, systemd-zram-generator, ffmpeg, imagemagick, python3-pip')
EXTRAS = 'mangohud, box64, dotnet-sdk-10.0, rustc, cargo, valgrind, heaptrack, godot-template-release'


def register(b):
    def build():
        src = b.OS / 'hw'
        p = b.Pkg('amerika-gamedev', b.DE_VERSION,
                  'Amerika game-development toolchain for Snapdragon X laptops\nCompilers, Vulkan/GL tools, profilers, benchmarks and the '
                  'amerika-hw tool: hardware report, temporary performance mode and opt-in system tuning (compressed swap, larger file-watch '
                  'limits, bigger shader cache).\nNothing is changed until you run "amerika-hw tune apply" or "amerika-hw perf game".',
                  depends='python3, pkexec, ' + TOOLCHAIN, recommends=EXTRAS, title='Amerika Game Dev Tools', category='Development')
        shutil.copytree(src / 'amerika_hw', p.path('/usr/lib/python3/dist-packages/amerika_hw'), ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        p.copy(src / 'bin/amerika-hw', '/usr/bin/amerika-hw', 0o755)
        p.copy(src / 'bin/amerika-hw-helper', '/usr/libexec/amerika/amerika-hw-helper', 0o755)
        p.copy(src / 'org.amerika.hw.policy', '/usr/share/polkit-1/actions/org.amerika.hw.policy')
        shutil.copytree(src / 'tuning', p.path('/usr/share/amerika-gamedev/tuning'))
        p.copy(b.ROOT / 'docs/hw/README.md', '/usr/share/doc/amerika-gamedev/README.md')
        p.scripts['prerm'] = ('#!/bin/sh\nset -e\nif [ "$1" = remove ] || [ "$1" = purge ]; then\n'
                              '  /usr/libexec/amerika/amerika-hw-helper tune revert >/dev/null 2>&1 || true\n'
                              '  /usr/libexec/amerika/amerika-hw-helper perf balanced >/dev/null 2>&1 || true\nfi\nexit 0\n')
        p.copyright('Amerika game-development tools, Copyright AltStack LLC, GPL-3.0-only.\n')
        return p
    return {'amerika-gamedev': build}
