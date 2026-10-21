# Amerika Agent development guide

Amerika Agent packages the published **OpenClaw 2026.10.5** npm distribution on Ubuntu ARM64. It is opt-in.
Node 24.16–24.x, libsecret-tools and an unlocked login keyring are required. Nothing uses `~/.openclaw`.
OpenClaw's MIT licence and all retained dependency notices ship in the package.

## First use

Open `amerika-settings agent`, choose Anthropic or OpenAI, and enter the API key there. The entry is cleared immediately
and the key is passed on stdin to Secret Service. Choose permissions, then start the gateway. Model entries come from
the pinned engine's catalogue, with offline defaults; catalogue membership does not establish account access or price.
Open the Agent window with Meta+A, the dock, bar chip or the optional Copilot-key selection.

Never pass a key as an argument or environment variable. For terminal use, `amerika-agent key set anthropic` prompts
through a hidden terminal reader. `amerika-agent key set openai` works the same way. A machine caller can pipe stdin.
Do not paste a key into the upstream owner console: use Amerika Settings for credential management.

## CLI contract

- `status --json`: installed/version, loopback gateway state, booleans for configured providers, model, permission mode,
  channels and autostart. Normal status uses cached provider booleans; it does not unlock the keyring.
- `key set|clear PROVIDER`: value on stdin or hidden terminal input for set; no value in output. Providers: anthropic/openai.
- `start`, `stop`, `restart`: control the user gateway service. Start validates/generated settings and resolves keyring refs.
- `enable [--now]`, `disable [--now]`: opt in/out of the Amerika session target's autostart. No package installation enables it.
- `config get [KEY] [--json]`, `config set KEY VALUE`: supported keys are model, mode, autostart, port, linux-node.
  Linux-node is experimental and off; it is not a supported desktop-control path for this release candidate.
- `models --provider anthropic|openai --json`: structured identifiers for the model picker. No model/provider request is made.
- `ask`: reads the prompt on stdin when no positional prompt is given. The native launcher uses stdin. The engine message
  file is private and removed afterwards; engine sessions/memory may retain conversation content.
- `dashboard-url`: prints only the clean loopback URL. The UI-only `--bootstrap` pipe mode obtains an upstream single-use
  browser handoff; it never falls back to placing the shared gateway token in a URL.
- `doctor`, `logs`: local diagnostics. Review logs before sharing them; sessions/engine errors may contain private content.
- `channels list|enable|disable`: opt-in external channels. Token material uses fixed SecretRefs and stdin.

The activity service listens on `$XDG_RUNTIME_DIR/amerika/agent-activity.sock` and writes private
`agent-activity.json` with `{state, text, since}`. The shipped plugin emits fixed non-content phases only.
See [the threat model](../THREAT-MODEL-AGENT.md) before enabling Trusted mode or external channels.

## Build and verify

`tools/fetch-openclaw.sh --offline` reuses an integrity-checked, pinned npm cache/stage. It starts with `npm ci --ignore-scripts`,
explicitly runs the audited OpenClaw postinstall, verifies ARM64 native prebuild loading, prunes unused platforms and
keeps licences. Any change to the fetch script or lock invalidates the stage stamp. Re-pin only with
`tools/fetch-openclaw.sh --update-lock VERSION`, then review all changes and repeat the full rig.

Build with `python3 build.py --only amerika-agent,amerika-desktop-shell,amerika-session` after installing build-essential
(or setting AMERIKA_CC). `--no-repo` builds without accessing any signing key. Development versions use
`dist/development`; the stable local repository remains in `dist/apt`. Node tools for a source checkout can be selected
with AMERIKA_NODE_BIN; runtime engine paths for disposable tests use AMERIKA_AGENT_ENGINE/NODE/SECRET_TOOL.
Never set those test overrides on an installed user service.

Run the unit suite and the private KWin rigs documented in [development testing](../DEVELOPMENT-TESTING.md).
The real-gateway rig uses a fake Secret Service, validates the generated config, probes the actual Amerika MCP server,
starts the actual gateway and renders the Control UI in ephemeral WebKit. It deliberately makes no model/provider call.

Recovery: `amerika-agent disable --now` stops autostart and the gateway. `amerika-agent key clear PROVIDER` removes that
provider key. These operations preserve workspace notes. To recover from bad config, stop the service first and use the
supported CLI/Settings controls to regenerate it; do not copy shared tokens or credentials into a support report.
