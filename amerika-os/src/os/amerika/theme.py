"""The Amerika retro-futurist look, shared by the shell and the settings app (GTK4 CSS)."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gtk  # noqa: E402

CSS = '''
@define-color am_bg #0b0a14;
@define-color am_panel #14131f;
@define-color am_panel_hi #22212f;
@define-color am_line #3a3950;
@define-color am_text #ecebf5;
@define-color am_dim #9a98b0;
@define-color am_accent %(accent)s;
@define-color am_second %(secondary)s;

* { font-family: "Inter", "Noto Sans", sans-serif; }
.am-mono, .am-clock { font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; letter-spacing: 1px; }
.am-label { font-size: 10px; font-weight: 700; letter-spacing: 2px; color: @am_dim; }

/* ---------- top bar ---------- */
window.am-bar, window.am-bar > * { background: transparent; }
.am-bar-box {
  background-image: linear-gradient(to bottom, #262535, #12111b);
  border-bottom: 1px solid alpha(@am_accent, .55);
  box-shadow: 0 1px 14px alpha(@am_accent, .35), inset 0 1px 0 alpha(white, .10);
  color: @am_text; padding: 0 10px; min-height: 36px;
}
.am-bar-btn {
  background-image: linear-gradient(to bottom, alpha(white, .10), alpha(white, .02));
  border: 1px solid alpha(white, .14); border-radius: 999px; color: @am_text;
  padding: 2px 12px; min-height: 24px; font-size: 11px; font-weight: 700; letter-spacing: 1.5px;
}
.am-bar-btn:hover { border-color: @am_accent; box-shadow: 0 0 10px alpha(@am_accent, .55); }
.am-bar-btn.ai { border-color: alpha(@am_second, .55); }
.am-bar-btn.ai:hover { border-color: @am_second; box-shadow: 0 0 12px alpha(@am_second, .65); }
.am-bar-icon { background: transparent; border: none; border-radius: 8px; padding: 3px 7px; color: @am_text; min-height: 24px; }
.am-bar-icon:hover { background: alpha(white, .10); }
.am-ai-chip {
  border-radius: 999px; padding: 2px 12px; font-size: 11px; font-weight: 800; letter-spacing: 1.5px;
  color: #0b0a14; background-image: linear-gradient(to right, @am_second, @am_accent);
  box-shadow: 0 0 14px alpha(@am_second, .7);
}
.am-ai-chip.idle { color: @am_dim; background-image: none; background: alpha(white, .06); box-shadow: none; }
.am-ai-stop { border-radius: 999px; padding: 2px 10px; background: alpha(@am_accent, .25); border: 1px solid @am_accent; color: white; font-size: 11px; font-weight: 800; }
.am-clock { font-size: 13px; font-weight: 600; color: @am_text; }
.am-appname { font-size: 12px; font-weight: 700; letter-spacing: 1px; color: @am_text; }

/* ---------- dock ---------- */
window.am-dock, window.am-dock > * { background: transparent; }
.am-dock-box {
  background-image: linear-gradient(to bottom, alpha(#2a2940, .88), alpha(#0f0e18, .92));
  border: 1px solid alpha(white, .22); border-radius: 26px; padding: 8px 12px;
  box-shadow: 0 10px 40px alpha(black, .65), 0 0 22px alpha(@am_accent, .28), inset 0 1px 0 alpha(white, .22);
}
.am-dock-item { background: transparent; border: none; border-radius: 16px; padding: 4px; margin: 0 2px; min-height: 0; min-width: 0; }
.am-dock-item:hover { background: alpha(white, .08); box-shadow: 0 0 18px alpha(@am_second, .45); }
.am-dock-ai { background-image: linear-gradient(to bottom, alpha(@am_second, .16), transparent); border: 1px solid alpha(@am_second, .35); }
.am-dock-dot { min-width: 18px; min-height: 3px; border-radius: 2px; background: @am_accent; box-shadow: 0 0 8px @am_accent; margin-top: 1px; }
.am-dock-sep { min-width: 1px; background: alpha(white, .18); margin: 8px 6px; }

/* ---------- launcher / overlays ---------- */
window.am-overlay { background: alpha(#05040a, .72); }
.am-panel {
  background-image: linear-gradient(to bottom, alpha(#24233a, .96), alpha(#0e0d17, .98));
  border: 1px solid alpha(white, .2); border-radius: 22px; color: @am_text;
  box-shadow: 0 24px 80px alpha(black, .75), 0 0 36px alpha(@am_accent, .25), inset 0 1px 0 alpha(white, .16);
}
.am-search { background: alpha(black, .45); border: 1px solid alpha(white, .18); border-radius: 14px; color: @am_text; padding: 10px 14px; font-size: 16px; min-height: 28px; }
.am-search:focus-within { border-color: @am_second; box-shadow: 0 0 16px alpha(@am_second, .5); }
.am-app { background: transparent; border: 1px solid transparent; border-radius: 16px; padding: 10px; color: @am_text; }
.am-app:hover, .am-app:focus { background: alpha(white, .07); border-color: alpha(@am_second, .6); }
.am-ask { background-image: linear-gradient(to right, alpha(@am_second, .20), alpha(@am_accent, .18)); border: 1px solid alpha(@am_second, .5); border-radius: 14px; padding: 10px 14px; color: @am_text; }
.am-ask:hover { box-shadow: 0 0 18px alpha(@am_second, .5); }

/* ---------- startup screen ---------- */
window.am-splash { background: #05040a; }
.am-splash-veil { background-image: radial-gradient(circle at 50%% 50%%, alpha(#05040a, .35), alpha(#05040a, .88)); }
.am-splash-word { font-size: 30px; font-weight: 800; letter-spacing: 11px; color: #f4f2fb; text-shadow: 0 0 22px alpha(@am_accent, .75); }
.am-splash-status { font-family: "JetBrains Mono", monospace; font-size: 11px; letter-spacing: 4px; color: @am_second; }
progressbar.am-splash-bar trough { background: alpha(white, .12); min-height: 4px; border-radius: 999px; }
progressbar.am-splash-bar progress { background-image: linear-gradient(to right, @am_second, @am_accent); min-height: 4px; border-radius: 999px; box-shadow: 0 0 14px alpha(@am_accent, .8); }

/* ---------- notifications ---------- */
.am-toast {
  background-image: linear-gradient(to bottom, alpha(#262540, .96), alpha(#0e0d17, .98));
  border: 1px solid alpha(white, .22); border-left: 3px solid @am_accent; border-radius: 16px; padding: 12px 14px; color: @am_text;
  box-shadow: 0 10px 34px alpha(black, .6), 0 0 18px alpha(@am_accent, .25);
}
.am-toast.ai { border-left-color: @am_second; }
.am-toast-title { font-weight: 800; font-size: 13px; }
.am-toast-body { font-size: 12px; color: @am_dim; }

/* ---------- buttons, dialogs, settings ---------- */
.am-primary { background-image: linear-gradient(to bottom, @am_accent, shade(@am_accent, .65)); color: white; border: 1px solid alpha(white, .35); border-radius: 12px; padding: 8px 18px; font-weight: 800; box-shadow: 0 0 14px alpha(@am_accent, .5); }
.am-secondary { background-image: linear-gradient(to bottom, alpha(white, .12), alpha(white, .03)); color: @am_text; border: 1px solid alpha(white, .2); border-radius: 12px; padding: 8px 18px; font-weight: 700; }
.am-dialog { background: @am_bg; color: @am_text; }
.am-card { background-image: linear-gradient(to bottom, alpha(white, .07), alpha(white, .02)); border: 1px solid alpha(white, .14); border-radius: 18px; padding: 16px; }
.am-heading { font-size: 22px; font-weight: 800; letter-spacing: .5px; }
.am-sub { color: @am_dim; font-size: 12px; }
window.am-settings { background: @am_bg; color: @am_text; }
.am-sidebar { background-image: linear-gradient(to bottom, #1a1930, #0d0c16); border-right: 1px solid alpha(white, .12); padding: 14px 10px; }
.am-side-item { border-radius: 12px; padding: 9px 12px; color: @am_text; background: transparent; border: 1px solid transparent; font-weight: 600; }
.am-side-item:hover { background: alpha(white, .06); }
.am-side-item:checked, .am-side-item.active { background-image: linear-gradient(to right, alpha(@am_accent, .35), alpha(@am_accent, .08)); border-color: alpha(@am_accent, .6); box-shadow: 0 0 14px alpha(@am_accent, .3); }
scale trough { background: alpha(white, .12); border-radius: 999px; min-height: 6px; }
scale highlight { background-image: linear-gradient(to right, @am_second, @am_accent); border-radius: 999px; }
scale slider { background: white; min-width: 16px; min-height: 16px; border-radius: 999px; box-shadow: 0 0 10px @am_second; }
switch { background: alpha(white, .14); border-radius: 999px; }
switch:checked { background-image: linear-gradient(to right, @am_second, @am_accent); }
switch slider { background: white; border-radius: 999px; }
entry, textview { background: alpha(black, .4); color: @am_text; border: 1px solid alpha(white, .16); border-radius: 10px; }
entry:focus-within { border-color: @am_second; }
separator { background: alpha(white, .12); min-height: 1px; min-width: 1px; }
listview, list { background: transparent; }
row { border-radius: 10px; }
row:selected { background: alpha(@am_accent, .25); }
'''


def apply(accent='#ff2e63', secondary='#19e3ff'):
    """Install the CSS for the default display. Returns the provider so callers can reload it."""
    provider = Gtk.CssProvider()
    provider.load_from_string(CSS % {'accent': accent, 'secondary': secondary})
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme', True)
    return provider
