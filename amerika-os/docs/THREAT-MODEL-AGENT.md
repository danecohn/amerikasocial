# Amerika Agent threat model

The local user controls the computer. The engine, installed packages and model provider are trusted software/services;
model output and everything obtained from documents, web pages or enabled channels are untrusted instructions.
This integration reduces the authority available to a model. It is **not an OS sandbox against malicious software
already running as the same Unix user**.

## Boundaries

- API keys and the shared gateway token are stored through the login Secret Service. The generated config contains
  exec SecretRefs. Provider credentials are not environment variables or command arguments. The helper accepts fixed
  credential names, bounded versioned requests, and refuses terminal output. Locked-keyring errors never cause token rotation.
- The gateway binds to loopback with token authentication, rate limiting, LAN discovery disabled, channels disabled,
  browser disabled, terminal/CLI-agent access disabled, automatic updates and background catalogue refresh disabled.
- The embedded WebKit session is ephemeral. A single-use pairing fragment becomes an administrator device credential
  in memory. Navigation is restricted to the configured `http://127.0.0.1:PORT` origin; external user-clicked links open
  in the normal browser. Downloads and device permissions are denied. External-browser fallback uses that browser's
  storage policy, rather than the embedded ephemeral profile.
- Native OpenClaw execution, filesystem, browser/UI, node and automation tool groups are denied in every mode.
  Mutating OS actions go through the fixed Amerika MCP server and the desktop broker. Web, memory and session tools
  remain enabled. Generated policy is validated against the pinned engine.
- The broker socket has a private runtime directory and same-UID peer checks. The wrapper fixes the client identity
  to `amerika-agent`. Client identity is a policy label, not cryptographic authentication of other same-UID programs.
- Read-only system facts can run without prompting. Sensitive content access requires approval in Ask/Balanced;
  Trusted permits sensitive actions. Shell execution, deletion and disruptive power actions require a fresh approval
  in every mode. The execution callback rechecks pause/disable after an approval resolves.
- Stop denies new broker calls, cancels approval requests and kills process groups of broker-created shell commands.
  It requests a gateway stop; the gateway unit uses control-group cleanup. Actions already completed cannot be undone.
- Activity contains only fixed labels, phases and opaque bounded session/run identifiers. No prompt, tool arguments,
  tool results or exception text is written to the activity file. The broker audit log does include bounded action
  arguments; treat it as private data. Screenshots, sessions and memory can also contain private information.

## Important limits

A shell command the user approves runs with their full account authority. Path restrictions on file tools do not
contain that command. Approval is meaningful only when the user understands the exact command shown.
The OpenClaw Control UI is an owner/admin console. An owner can edit its advanced configuration, install plugins or
replace SecretRefs; such owner changes can weaken these defaults or store credentials in plaintext. Use **Amerika
Settings → Amerika Agent** for API keys and supported configuration. The integration does not claim to prevent the
computer's owner from changing their own files or engine policy.

Provider requests send the chosen conversation/tool context to that provider and can incur charges. Real provider
requests and billing were not exercised by the integration rig; it uses fake keyring values and makes no model call.
The pinned upstream includes its own trust assumptions and vulnerabilities. Pinning and npm integrity checks establish
which bytes were installed, not that every dependency is safe.

Channels increase exposure to prompt injection and unwanted tool requests. Unknown senders use upstream pairing;
that is not a substitute for local approvals. Channels are opt-in, and the default mode is Ask. Never automatically
approve a remote request because it calls itself the owner.

Clipboard history is bounded text in process memory with no persistence. Password-manager MIME hints and explicit
sensitive clipboard state are skipped where supplied. A clipboard value without such a hint cannot reliably be
identified as a password. Background tracking requires compositor data-control support; GDK has a focus-limited fallback.

A GTK overlay is not a secure lock screen. This development build does not claim a reviewed, independent Amerika
screen lock. Secure session locking, suspend/resume, multi-monitor protection and recovery remain release gates.
