# Putting the pack on your iPhone

iOS has no public "icon pack" format, so the pack works the way every iOS theme does: a Shortcut opens the app, and the Home Screen icon for that Shortcut is one of these images.

## One icon
1. Save the PNG from `icons/night/` (dark) or `icons/rose/` (pink) to Photos or Files. On the gallery page, tap an icon to download it.
2. Open **Shortcuts**, tap **+**, choose **Open App**, and pick the app.
3. Tap the shortcut's name at the top, **Add to Home Screen**, then tap the icon square and choose **Choose Photo** or **Choose File** and pick the image. Name it, then **Add**.
4. Hide the original app icon from the Home Screen (long-press, **Remove from Home Screen**, **Remove from Home Screen** keeps the app in the library).

iOS rounds the corners itself, so the images are full-bleed squares. Keep the glyph inside the middle 80% if you make your own.

## Wallpapers
`wallpapers/*.png` are 1290x2796. Settings, Wallpaper, Add New Wallpaper, Photos. The top third is left calm for the clock.

## Widget covers
`widget-covers/plain/` has six styles in small (474x474), medium (1014x474) and large (1014x1062). `widget-covers/labeled/` has covers with a label (Weather, Calendar, Music and more). Use them as the background image in a widget app such as Widgetsmith or Color Widgets.

## Your own icons
`node tools/ios/build-icons.js <id>` re-renders one icon. A new icon is one line in `tools/ios/apple.js`, `apps.js` or `vigil.js`: pick a background (`rose`, `deep`, `wine`, `magenta`, `plum`, `blush`) and draw with the glyph primitives in `tools/ios/engine.js`. The `blank` tile and the faith set in `icons/*/faith/` work for any app that is not in the pack.

## Licence
GNU GPL v3. Share it, change it, pass it on.
