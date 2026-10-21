# Desktop integration APIs

The shell owns `org.amerika.Shell` on the session bus. `/Control`, interface `org.amerika.Control`, accepts `Action(s)`.
Supported surfaces include launcher, agent, settings, lock request, global AI stop, overview, `switcher:next|prev|app-next`,
clipboard, calendar, `screenshot:region|window|screen`, `record:toggle`, hardware `osd:*` and `media:*` actions.
These are same-user UI APIs; they are not an authentication boundary for untrusted local software.

KWin reports window/desktop state to `/Windows`, `org.amerika.Windows.Report(s)`. The bridge obtains current hot-corner,
touch-edge and snap-gap configuration from `/Desktop`, `org.amerika.Desktop.Config() -> s`. New one-shot window commands
use fixed templates with validated IDs and JSON-encoded strings. The pager and picker share that window registry.

The native shell host links Ubuntu's maintained Python shared library. Its dedicated executable path matches the
`org.amerika.Shell.desktop` restricted-interface declaration, so KWin can authorise screenshot requests specifically
for that host instead of the generic Python interpreter. This follows KWin 6.7's executable/desktop-file matching in
[serviceutils.h](https://github.com/KDE/kwin/blob/Plasma/6.7/src/utils/serviceutils.h) and its
[screenshot permission check](https://github.com/KDE/kwin/blob/Plasma/6.7/src/plugins/screenshot/screenshotdbusinterface2.cpp).
No permission-check bypass environment variable is used. The private rig exercises the real compiled host and capture.

Window thumbnails use that authorised capture interface and fall back to application icons on capture failure.
The switcher accepts Alt release, Enter, Escape and pointer selection. The overview searches window titles and offers
window commands and desktop navigation. Physical key-release timing/touch ergonomics still need laptop verification.

Recording currently uses modest-rate KWin frames encoded with GStreamer when a direct compositor recorder is unavailable.
This is not a validated PipeWire portal recorder and does not record microphone/system audio. The bar shows recording
state. Output capture, region/window selection and annotation are provided by ScreenshotService.

Settings owns `org.amerika.Settings`, `/org/amerika/Settings/Control`, with OpenPage/Pages/Get/Set/Schema. Deep links are
`amerika-settings PAGE`; `--list` works without a display. Set is a strict allowlist of appearance/clock/Copilot settings.
There is no arbitrary method dispatch, privileged package argument or API-key interface on this settings API. Model
mutations continue to pass through the MCP broker; this ordinary same-UID D-Bus API is for local applications.
