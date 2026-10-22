#!/bin/sh
# Boot smoke test: the shell must come up (shell-ready file written, no Traceback) with every look/dock/home combination.
# Run inside tests/rig/claude_os_rig.sh:  sh tests/rig/claude_os_rig.sh "sh tests/rig/shell_boot_test.sh"
fail=0
for combo in "retro bottom off" "tesla right claude" "tesla left chatgpt" "tesla bottom off" "retro right claude"; do
  set -- $combo
  mkdir -p "$XDG_CONFIG_HOME/amerika-os"
  cat > "$XDG_CONFIG_HOME/amerika-os/settings.json" <<EOJ
{"ui_style":"$1","dock_position":"$2","home_mode":"$3","dock_enabled":true,"bar_preset":"home","copilot_app":"caster"}
EOJ
  rm -f "$XDG_RUNTIME_DIR/amerika/shell-ready"
  out="$T/boot-$1-$2-$3.out"
  amerika-shell > "$out" 2>&1 &
  pid=$!
  n=0
  while [ $n -lt 40 ] && [ ! -f "$XDG_RUNTIME_DIR/amerika/shell-ready" ]; do sleep 0.5; n=$((n + 1)); done
  if [ -f "$XDG_RUNTIME_DIR/amerika/shell-ready" ] && kill -0 $pid 2>/dev/null && ! grep -q Traceback "$out"; then
    echo "PASS boot: $combo"
  else
    echo "FAIL boot: $combo"; grep -A12 Traceback "$out" | head -20; fail=1
  fi
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
done
exit $fail
