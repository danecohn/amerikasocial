# Artemis Softworks LLC — identity and product direction

AltStack is an alternative stack for everyone: open-source social, productivity, browsing, and creative tools, running on your computer and in the cloud where each product supports it.

## Approved logo

The official logo is the owner-supplied pink, black, and white AS/arrow artwork. `altstack-logo-original.png` is byte-for-byte identical to the provided file. The SVG files embed that PNG losslessly; they are compatibility containers, not vector tracings. The discarded blue stack symbol is not part of this identity. No replacement monochrome logo is approved.

Keep the image proportions and full artwork. Preserve its pink background and black outlines. Use at least one-eighth of the logo width as clear space outside its existing canvas. Use a 32px or larger display when space permits; favicon derivatives are provided for constrained contexts. A true vector master and optically simplified small-size mark can be developed from the supplied artwork as a later design task.

## Product architecture

| Family name | Short name | Current foundation |
| --- | --- | --- |
| AltStack Social | Social | Existing AT Protocol/PDS integration and local account system |
| AltStack Venture | Venture | Firefox engine distribution with downstream resources |
| AltStack Office | AltOffice | Euro-Office fork/integration |
| AltStack Render | Render | Blender add-on and launcher |
| AltStack Engine | Engine | Godot plugin, assembler, and launcher |
| AltStack Sprite | Sprite | Original pixel-art editor |
| AltStack Box | Box | BeepBox-based chiptune editor |
| AltStack Desktop | Desktop | Existing Ubuntu/KWin desktop-environment project |

AmerikaLinux, AmerikamacOS, and AmerikaWindows contain native **Social clients**, not three separate operating systems. They become AltStack Social for Linux, macOS, and Windows. Keep their repository URLs valid until repository renames are deliberately coordinated.

## Alpine interface system

The reference is Snow Leopard's calm desktop material language, interpreted with original assets and modern accessibility: silver toolbars, restrained bevels, frosted panels, glacier-blue focus and selection, and readable dark text. The official pink logo is the brand anchor; blue is an interface action color. Avoid neon grids, decorative glow around text, giant empty dashboards, or low-contrast gray labels.

Canvas `#e7edf3`; surface `#f8fafc`; chrome `#cbd5df`; ink `#233649`; muted text `#51677c`; border `#aebdcb`; action `#1764bd`; brand pink `#ff0058`. Use Inter or the system sans-serif stack. Controls have 6px corners, panels 12–14px. Use native platform controls where appropriate. Do not reproduce Apple icons, system sounds, or proprietary artwork.

Retain visible keyboard focus, reduced-motion behavior, meaningful control labels, and responsive navigation. State hover, active, selected, and disabled appearances consistently. Creative canvases can retain content-specific colors and neutral working spaces.

## Voice

Core promise: **An alternative stack for everyone.**

Welcome line: **Welcome to AltStack.**

Explain where work lives and which functions require a hosted service. Do not claim every app works offline, that the current Office wrapper is a fully rebuilt native editor, or that a launcher integration is a rewritten upstream engine. Keep Euro-Office, Mozilla, Blender, Godot, BeepBox and other upstream attribution and licenses intact.

## Domains

`altstack.io` is the public home and Social web origin. This source pass keeps the Social application at `/` and adds the ecosystem introduction at `/welcome`, avoiding a rushed rewrite of its authentication and API routes. `office.altstack.io` is the proposed Office origin. `altstack.social` is the planned PDS origin and handle domain. Additional application subdomains are proposals, not provisioned services.

## Compatibility

Visible product names, website copy, company names, logos, icons, and selected interface themes are updated. Internal `amerika`, `makk`, bundle IDs, database keys, credential identifiers, application paths, package names, file formats, API contracts, existing GitHub URLs, and upstream identifiers remain where required for compatibility. These are not a substitute for a signed, tested migration release. Existing settings and account storage must not be reset merely to remove an old internal name.
