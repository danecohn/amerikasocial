# amerika-studio-webview: contract for Sprite and Box

`amerika-studio-webview` is the shared GTK4 + WebKitGTK 6.0 window that hosts the two
web-based apps (Amerika Sprite, AmerikaBox). The app is a static directory of HTML/JS/CSS
(no server, no Node). The shell gives the page a tiny, token-free JS bridge, file dialogs,
recent files, drag-drop, and an app control endpoint so Amerika Agent (via
`amerika-studio-mcp`) can drive the page.

## Launching

```
amerika-studio-webview --app sprite|box --dir /usr/share/amerika-sprite/app [--entry index.html]
                       [--title "Amerika Sprite"] [--icon amerika-sprite] [--app-id org.amerika.Sprite]
                       [--project-dir ~/Studio/Sprite] [FILE ...]
```

* `--app` is `sprite` or `box` (selects defaults for title, icon, app id, file filters,
  project dir `~/Studio/Sprite` / `~/Studio/Box`, and the bridge `X-Amerika-App` value).
* `--dir` is the app directory; the page is `file://<dir>/<entry>`.
* `FILE` arguments are opened after the page signals it is ready (`onOpen`).
* The launchers `amerika-sprite` / `amerika-box` (owned by the sprite/box engineers) are
  shell scripts that `exec amerika-studio-webview --app ... --dir ...`. Single instance
  per app: a second launch with a live control endpoint forwards its FILE arguments
  (`app.open` RPC -> `onOpen`) and exits.

## Page environment

* Origin is `file://`. Navigation is restricted: the top frame may only load `file://`
  URLs below `--dir` (or `/usr/share/amerika-studio/web`); `http(s)`, `ftp`, other
  `file://` paths and new windows are refused (links with `target=_blank` are dropped).
* The page has **no network**: a WebKit content blocker (installed before the first load; if it cannot
  be installed the page is not loaded at all) drops every `http(s)://`, `ws(s)://` and `ftp://` request,
  including `<img>`, `<script>`, `fetch()`, `XHR` and WebSockets. A CSP `<meta>` (local resources only)
  is injected as a second layer. Use `amerikaStudio.request` for the AI. Do not load fonts, scripts or
  images from a CDN; ship everything inside `--dir`.
* `fetch("data.json")` of local files works, but `Response.ok` / `status` are not meaningful for `file://`
  (status is 0): just `await res.text()` / `res.json()` and catch errors.
* All WebKit permission requests (camera, mic, geolocation, notifications) are denied; downloads are
  cancelled (use `fs.save`). Developer extras are off unless `AMERIKA_STUDIO_DEVTOOLS=1` (then
  right-click > Inspect works).
* `localStorage` works (persisted in `~/.local/share/amerika-studio/<app>/webdata`).
* The shell injects, at document start, `window.amerikaStudio` and
  `window.amerikaStudio.AIClient` (see below). The page does NOT need to include anything.
* Shared look: `<link rel="stylesheet" href="file:///usr/share/amerika-studio/web/studio.css">`
  gives the `am-*` retro-futurist tokens (CSS variables `--am-bg`, `--am-neon`,
  `--am-chrome`, ...). Optional.

## `window.amerikaStudio` (all methods return Promises; JSON in, JSON out)

The token and API key never reach page JS. Calls go through a WebKit script-message
handler (`webkit.messageHandlers.amerika`) to the Python shell, which adds the token.

| Member | Description |
|---|---|
| `info` | (sync object) `{app, version, projectDir, shell:"amerika-studio-webview"}` |
| `request(path, body, opts?)` | POST JSON to the bridge: `path` must be `/v1/messages` and `body` the Messages API body (model allowlist `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-haiku-5-5`; `max_tokens` <= 16000; no `stream`). GET forms: `request("/v1/status")` (`{key:{sprite:bool,...}, default_model, budget:{daily_tokens, used_today}}`) and `request("/v1/models")` (body omitted -> GET). Anything else rejects. Resolves `{status, json, headers}` for every HTTP answer (including 4xx/5xx, so the page can show `json.error.message`; `headers` holds `retry-after` when sent). Rejects with an `Error` (`.error` = `bridge_down`, `.message`) only for transport failures; the shell starts the bridge (`amerika-studio ensure`) once automatically if it is down. `opts: {timeoutMs}` (default 300000). The shell sets `X-Amerika-App` itself. |
| `fs.open({title?, filters?, binary?})` | Native open dialog. `filters: [{name:"Sprites", patterns:["*.png","*.aseprite"]}]` (defaults per app). Resolves `null` if cancelled, else `{path, name, binary, data}` where `data` is UTF-8 text, or base64 when `binary:true`. Size cap 64 MiB. Adds to recent files. |
| `fs.save({title?, suggestedName?, data, encoding?, filters?})` | Native save dialog (starts in the project dir). `encoding: "utf8"` (default) or `"base64"`. Resolves `null` if cancelled, else `{path, name}`. Confirms overwrite. |
| `fs.readFile(path, {binary?})` | Read a file that was previously returned by `fs.open`/`fs.save`/`recent.list`, or that lives inside the project dir. Else rejects `path_not_allowed`. |
| `fs.writeProject(relPath, data, {encoding?, overwrite?})` | Write inside the project dir (confined: no absolute path, no `..`, no symlink escape). Resolves `{path}`. This is what exports triggered by MCP use. |
| `fs.listProject(relDir?)` | `[{name, dir, size}]` inside the project dir. |
| `recent.list()` / `recent.add(path)` / `recent.clear()` | Recent files for this app (`~/.local/state/amerika-studio/recent-<app>.json`, max 12). Shown in the shell's "Open recent" menu button. |
| `window.setTitle(s)` | Window title becomes `s - Amerika Sprite`. |
| `window.setDirty(bool)` | If true, closing the window asks to discard changes. |
| `window.close()` | Close the window. |
| `ai` / `AIClient` | `new amerikaStudio.AIClient({model?, system?, tools:[{name,description,input_schema}], run:async (name,input)=>result, maxTurns?:12, maxTokens?:4096})`; `.send(text, {images?})` runs the tool-use loop (non-streaming) via `request`, returns `{text, toolCalls, usage, stopped}`; `.stop()` sets the stop flag; `.reset()`. Results from `run` may be a string/object or `{text?, image?:{mime,base64}}`. Errors (401, 429/529 with retries, budget) become `Error` with `.code`. |

Page-implemented hooks (assign them):

| Hook | Called by shell |
|---|---|
| `amerikaStudio.onOpen = async (file) => {}` | `file = {path, name, binary, data}`: CLI args, drag-drop, "Open recent", `app.open` RPC. The shell decides `binary` from the extension (`.png .gif .aseprite .wav .ogg .mp3 ...` binary). Drag-drop of several files calls it once per file. |
| `amerikaStudio.onRpc = async (method, params) => result` | Control endpoint. `method` is the tool name WITHOUT the app prefix as in `tools.json` (e.g. `"canvas.info"`, `"song.set"`, `"app.prompt"`). Return a JSON-able object (images as `{images:[{mime,base64}]}`), or throw `Error` (message is returned to the agent; set `err.code` to a JSON-RPC code from `tools.json` conventions, default -32000). Unknown method: throw with `code = -32601`. |
| `amerikaStudio.onBeforeClose` | Not provided; use `window.setDirty`. |

Setting `onRpc` marks the page ready; `app.ping` returns `ready:false` until then.

## Control endpoint

The shell starts a loopback HTTP server on an ephemeral port `127.0.0.1:P` with a random
token and writes `$XDG_RUNTIME_DIR/amerika/studio-<app>.json` (mode 0600):
`{"app":"sprite","url":"http://127.0.0.1:P","token":"...","pid":N,"version":"..."}`; removed
on exit. `POST /rpc` with `Authorization: Bearer <token>`, JSON-RPC 2.0, `method` is
`<app>.<tool>` (e.g. `sprite.canvas.info`) exactly as in `src/os/studio/tools.json`. The
shell strips the app prefix and delegates to `onRpc`, except these shell-level methods:

* `<app>.app.ping` -> `{ok:true, app, version, ready}`
* `<app>.app.open` `{path}` -> forwards to `onOpen`
* `<app>.app.screenshot` -> `{images:[{mime:"image/png",base64}]}` of the page

Only one RPC is delegated at a time (the page is single-threaded); a concurrent call gets
error `-32002` (busy). Default timeout is the tool's `timeout` from `tools.json` (the MCP
server passes it as header `X-Amerika-Timeout`), capped at 900 s; on expiry `-32000
timeout`.

## Writing the page: checklist

1. Implement `onRpc` for every non-shell tool of your app in `tools.json`, with exactly the
   input schema and return JSON described there. Validate inputs; export paths go through
   `fs.writeProject`.
2. Your AI panel uses `amerikaStudio.AIClient` with your tools; `app.prompt` should feed the
   same panel (append the message as if the user typed it, run, return the final text).
3. Never store or ask for an API key in the page. If `AIClient` rejects with `code === "no_key"`
   (or `request("/v1/status").json.key.<app>` is false), tell the user to press the shell's
   **Keys...** toolbar button (it launches `amerika-studio-keys --app <app>`) or to use Amerika Studio, then
   retry; no restart is needed.
4. Test in a browser if you like: when `window.amerikaStudio` is absent (plain browser),
   load `/usr/share/amerika-studio/web/dev-shim.js` (mock bridge; ships with the package)
   to get an in-memory `amerikaStudio` for UI work.
