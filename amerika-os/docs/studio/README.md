# Amerika Studio (Developer Edition)

Amerika Studio is the shared layer under four apps where you describe what you want and Claude builds it:
**Amerika Render** (Blender + add-on), **Amerika Engine** (Godot + plugin), **Amerika Sprite** (original pixel-art editor in a
WebKitGTK window) and **AmerikaBox** (BeepBox fork in a WebKitGTK window). This document covers the shared layer owned by
`studio-core`: key handling, the bridge, the tool-use loop, the MCP server, the hub, the web shell and packaging. The product
architecture and licensing notes are in `docs/STUDIO-ARCHITECTURE.md`; the web shell contract is in [webview.md](webview.md).

Install: `sudo apt install amerika-developer` (meta package, **opt-in**: it is not a dependency of `amerika-desktop`).
Nothing is started or enabled at install time.

## Pieces

| Component | What it is |
|---|---|
| `amerika_studio` (Python, `/usr/lib/python3/dist-packages`) | `keyring`, `client` (bridge client + tool-use loop), `prompts`, `usage`, `confine`, `bridge`, `mcp`, `control`, `webcore`/`webview`, `hub`, `keys`, `approve`, `cli` |
| `amerika-studio-bridge` + `amerika-studio-bridge.service` (systemd `--user`) | loopback proxy `127.0.0.1:18890` to `api.anthropic.com`; started on demand by `amerika-studio ensure` |
| `amerika-studio` | CLI: `ensure`, `status [--json]`, `key set\|clear\|status [--app A]`, `budget [--set N]`, `config model\|reuse-agent-key\|agent-tools\|override`, `new-game NAME` |
| `amerika-studio-hub` | the "Amerika Studio" app: four tiles, key setup, model, budget, New game, recent, Amerika Agent switch |
| `amerika-studio-keys` | small dialog for the Anthropic key (`--app render` for a per-app key) |
| `amerika-studio-webview` | WebKitGTK shell for Sprite and Box ([webview.md](webview.md)) |
| `amerika-studio-mcp` | stdio MCP server for Amerika Agent (`render_*`, `engine_*`, `sprite_*`, `box_*`, `studio_status`, `studio_launch`) |
| `amerika-studio-approve` | the "Run it / Decline" dialog used by the MCP server for tools that execute code |
| `/usr/share/amerika-studio/tools.json` | the ONE tool catalogue the four apps implement and the MCP server serves |
| `/usr/share/amerika-studio/web/` | `shell.js` (injected bridge), `ai-client.js` (JS tool-use loop), `studio.css`, `dev-shim.js` |
| Settings > Amerika Studio | `amerika/settings/page_studio.py`: key, model, budget, agent switch, open hub |

## Key flow

1. The user enters the key in the hub ("Set up Anthropic key"), in Settings > Amerika Studio, via `amerika-studio-keys`, or
   `amerika-studio key set [--app render]` (stdin only; a TTY prompt is hidden).
2. The GTK dialogs read the `Gtk.PasswordEntry`, clear it immediately and hand the value to the keyring helper in a worker
   thread. The UI then only shows "Key saved in your keyring" or "No key saved".
3. The keyring helper runs `secret-tool store` with the value on **stdin**. Attributes: `service=amerika-studio name=anthropic`
   (shared), `name=anthropic-<app>` (per-app override, apps `render engine sprite box`). Optional fallback to Amerika Agent's key
   (`service=amerika-agent name=anthropic`) when the "reuse" switch is on. The key is never in argv, the environment, a file, a
   log, git or a test (tests use `sk-ant-test-FAKE...` and a fake `secret-tool`).
4. Selection per request: the bridge looks at `X-Amerika-App` (`render|engine|sprite|box|agent|hub`). For an app: its own key if
   stored and its override toggle is on, else the shared key, else (if enabled) the agent key. Missing key -> `403 no_api_key`,
   which the client maps to "Set up Anthropic key". Missing keys are never cached, so saving a key works immediately.

## Bridge

`POST /v1/messages` (Messages API body, non-streaming), `GET /v1/status`, `GET /v1/models`, `GET /v1/ping` (no auth). Auth is a
per-user token in `$XDG_RUNTIME_DIR/amerika/studio-token` (mode 0600, created by the bridge, stable across restarts of the same
login session). Apps read it from the file (Blender/Godot) or never see it (web apps: the shell adds it).

Validation before anything leaves the machine: JSON object only; only the fields `model, max_tokens, messages, system, tools,
tool_choice, temperature, top_p, top_k, stop_sequences, thinking` (and `stream: false`); model in `claude-sonnet-5-5` (default),
`claude-opus-5-5`, `claude-haiku-5-5`; `max_tokens` <= 16000; body <= 12 MiB; <= 400 messages; <= 128 tools and only custom (client)
tools, so no server-side web search or code execution can be smuggled in. A daily token budget (default 2,000,000, `0` =
unlimited; `amerika-studio budget --set N`) returns `429 budget_exceeded`. Upstream errors are passed through with their status and
`retry-after`; transport failures become `502 bridge_upstream_unreachable`. The usage log
(`~/.local/state/amerika-studio/usage.jsonl`) holds time, app, model and token counts only.

Tests may point the bridge at a fake upstream with `AMERIKA_STUDIO_UPSTREAM=http://127.0.0.1:PORT`; any non-loopback value is
ignored, so a stray variable can never redirect the key. `AMERIKA_STUDIO_PORT` changes the port (tests, rigs).

## Using Claude from an app

* **Python (Blender add-on, Sprite/Box backends, tests):** `from amerika_studio import client, prompts`;
  `c = client.BridgeClient("render")`; `res = client.run_loop(c, messages=[...], tools=[...], handler=fn, system=prompts.system_prompt("render"), max_turns=12, stop=event)`.
  The loop is non-streaming, handles `tool_use` / `tool_result` / images (a handler may return `{"images":[{"mime","base64"}]}`),
  turns handler exceptions into `is_error` results the model can recover from, stops on `stop.set()` without leaving unanswered
  `tool_use` blocks, and `BridgeClient.messages` retries 429/529/502/503 with exponential backoff (honouring `retry-after`, not for
  budget/no-key/auth errors). `client.ApiError.kind` is one of `bridge_down bridge_auth no_key key_rejected budget rate_limit
  overloaded invalid_request too_large server stopped`.
* **Godot (GDScript):** `HTTPRequest` to `http://127.0.0.1:18890/v1/messages` with `Authorization: Bearer <token file contents>` and
  `X-Amerika-App: engine`. Same JSON.
* **Web apps:** `amerikaStudio.AIClient` (see [webview.md](webview.md)).

## App control endpoints and the MCP server

Every running app opens a loopback JSON-RPC server (token) and writes `$XDG_RUNTIME_DIR/amerika/studio-<app>.json`
= `{app,url,token,pid,version}` (mode 0600, removed on exit). `amerika-studio-mcp` reads `tools.json`, exposes each tool as
`<app>_<tool with dots as underscores>` (e.g. `render_scene_run_python`), validates arguments against the schema, forwards the call
as `POST <url>/rpc` JSON-RPC method `<app>.<tool>` (e.g. `render.scene.run_python`) with the tool's `timeout`, and returns the
result (images become MCP image content). If the app is not running, the MCP server starts it through its launcher
(`amerika-render|engine|sprite|box`) and waits until `<app>.app.ping` says `ready` (disable with
`AMERIKA_STUDIO_MCP_AUTOLAUNCH=0`; or call `studio_launch`). Descriptors that are group/world accessible, not loopback, or whose
`pid` is gone are ignored.

Enabling it for Amerika Agent: the hub switch / Settings switch / `amerika-studio config agent-tools on` set `studio_tools` in
Amerika Agent's settings and run `amerika-agent config apply`, which adds `mcp.servers.amerika-studio` (and allows
`amerika-studio__*`) to the generated OpenClaw config. Off by default.

### Adding or changing a tool

1. Edit `src/os/studio/tools.json` (name, description, `risk` read|act|critical, `timeout` seconds, JSON Schema `inputSchema` with
   `additionalProperties:false`). Names are `<area>.<action>` and must give a valid Anthropic tool name after the prefix and the
   dot-to-underscore mapping (the unit tests check this).
2. Implement the RPC method `<area>.<action>` in the app (Blender add-on, Godot plugin, or the page's `onRpc`) with the same
   schema, returning a JSON object. Error codes: `-32601` unknown method, `-32602` invalid params, `-32001` user denied,
   `-32002` busy, `-32003` path outside project, `-32004` not ready, `-32000` other.
3. Run `python3 -m unittest tests.test_studio_core`. The schema validator, MCP listing and risk annotations come from the file.

Every app must implement `app.ping` (returns `ready`) and `app.prompt` (feeds the app's own assistant panel and returns the final
reply). `risk: critical` (code execution, e.g. `render.scene.run_python`) makes the MCP server ask the user for approval through
`amerika-studio-approve` **every time**, in every Amerika Agent mode. If the dialog cannot be shown, the answer is no.

## Security model

* Keys only in the Secret Service; only the bridge reads them; apps never see them; no key in argv/env/files/logs/tests.
* The bridge listens on loopback only, requires the token (constant-time compare), refuses browser `Origin` headers and foreign
  `Host` headers (DNS rebinding), caps sizes, allows only whitelisted models and client tools, and enforces a daily token budget.
* Web apps run with no network (content blocker + CSP), restricted navigation, no permissions, and a message-handler bridge that
  keeps the token on the Python side. File access from the page is limited to user-picked files, recent files and the project
  folder.
* All file tools are confined to the project directory (`~/Studio/<App>/...`): absolute paths, `..`, NUL bytes and symlinks that
  leave the project are refused (`amerika_studio.confine`). Overwriting needs an explicit flag; deleting or overwriting outside a
  project is never offered.
* Code written by the model (bpy Python, GDScript) is shown, undo-checkpointed and run only inside the apps ("Review before run" on
  by default for `exec`-style tools); the MCP route adds the approval dialog above. No shell command from the model is ever run.
* The control endpoints and descriptors are per-user, 0600, loopback, token-authenticated, and serve one call at a time.
* Blender, Godot and BeepBox keep their licences and trademarks; the UI says "powered by". Aseprite is not used or copied.

## Files

```
src/os/studio/{amerika_studio/,bin/,web/,systemd/,applications/,icons/,tools.json}   tools/make_studio_icons.py (regenerates icons)
src/os/amerika/settings/page_studio.py   src/os/agent/amerika_agent/config.py (studio_tools)
tools/builders/{studio,developer}.py     tests/test_studio_core.py   tests/rig/studio-rig.sh + studio_*_test.{py,sh}
```

## Testing

* `python3 -m unittest discover -s tests -q` (no network, fake `secret-tool`, fake upstream, canned tool-use responses).
* GTK/WebKit rig (headless KWin on a private D-Bus, own Wayland socket): `tests/rig/studio-rig.sh tests/rig/studio_hub_test.sh`
  (hub, keys dialog, Settings page) and `tests/rig/studio-rig.sh tests/rig/studio_webview_test.sh` (web shell end to end: JS bridge,
  proxy through a real bridge to a fake upstream, tool loop in the page, confinement, no-network and navigation checks, control
  endpoint, MCP). Screenshots land in `dist/studio/`.
