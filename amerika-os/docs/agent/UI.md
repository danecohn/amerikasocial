# Agent UI contract

The GTK frontend calls `amerika-agent` on worker threads. API keys and prompts travel on stdin. The key entry clears
before the worker is started; output is scrubbed of the just-submitted value. The model picker consumes structured
`models --json` output. Stop/Start status, provider booleans, onboarding and error/missing-package states are covered by
unit tests and seven Settings screenshots in the private rig.

The Agent window uses WebKitGTK 6 with `NetworkSession.new_ephemeral()`. Cookies, device credentials and browser
storage are not persisted by the embedded session. Only the configured loopback origin can navigate in that view.
A normal browser fallback has the browser's own storage behaviour. The embedded upstream console is an owner console,
not a reduced-privilege chat view; advanced settings can override defaults. API keys belong in the native Settings page.

The shell watches non-content activity, displays its chip, routes Meta+A/Copilot/launcher prompts and couples the global
Stop switch to gateway stop. Closing an Agent window does not disable autostart; closing the Amerika session target
stops the gateway. A launcher answer is not proof that every requested action completed: tools report their own errors.
