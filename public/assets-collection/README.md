# VigilTech iOS 27 icon pack

A full iOS 27 reskin in the VigilTech look: pink `#ff0058`, plum-black, candlelit, with a quiet gothic streak. **160 icons in two looks (Rose and Night = 320 images at 1024x1024), 6 wallpapers (1290x2796), 6 widget-cover styles in 3 sizes, 40 labelled covers and 32 covers with short Latin phrases.**

Everything here is free software under the **GNU GPL v3**.


Open `index.html` (serve the folder, for example `python3 -m http.server`, or turn on GitHub Pages) for the gallery. See `INSTALL.md` to use the icons.

| Folder | What |
| --- | --- |
| `icons/{rose,night}/apple/` | 54 native Apple apps: Phone, Messages, FaceTime, Mail, Safari, Maps, Photos, Camera, Music, Keynote, Pages, Numbers, Passwords, Journal, Wallet, Settings and the rest |
| `icons/*/apps/` | 56 popular apps: Instagram, WhatsApp, TikTok, YouTube, Spotify, Discord, ChatGPT, Claude and more |
| `icons/*/faith/` | 36 icons for faith apps: cross, crucifix, rosary, Bible, Sacred Heart, chalice, angel, Mass times, rose window and more. |
| `icons/*/vigiltech/` | 14 VigilTech apps |
| `wallpapers/` | The Nave, Our Lady, Star of Bethlehem, Rose Window, Paschal Dawn, Candlelight |
| `widget-covers/` | plain, labelled, and short Latin phrases |

Every glyph is drawn from signed-distance shapes at its final size (nothing is scaled up), then lit with a bevel read from the shape, a drop shadow, glass, and the four-point glint. Lettering is set in Vigil Sans (`fonts/`, OFL 1.1). Images are written with the Sprite engine's PNG encoder (`tools/sprite/`); Sprite documents top out at 512 pixels, so the larger masters are drawn natively at full size rather than inside a Sprite canvas.

Rebuild: `node tools/ios/build-icons.js && node tools/ios/build-scenes.js` (Node 20+, no dependencies).

App names and the shapes of third-party marks belong to their owners; these are simplified VigilTech-style artwork for personal Home Screen customisation. Code and artwork: GPL v3 (`LICENSE`). Font: SIL OFL 1.1.
