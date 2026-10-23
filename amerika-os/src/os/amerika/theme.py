"""The Amerika retro-futurist look, shared by the shell and the settings app (GTK4 CSS)."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gtk  # noqa: E402

CSS = '''
@define-color am_bg #e7edf3;
@define-color am_panel #f8fafc;
@define-color am_panel_hi #dde6ef;
@define-color am_line #aebdcb;
@define-color am_text #233649;
@define-color am_dim #51677c;
@define-color am_accent %(accent)s;
@define-color am_second %(secondary)s;

* { font-family: "Inter", "Noto Sans", sans-serif; }
.am-mono, .am-clock { font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; letter-spacing: 1px; }
.am-label { font-size: 10px; font-weight: 700; letter-spacing: 2px; color: @am_dim; }

/* ---------- top bar ---------- */
window.am-bar, window.am-bar > * { background: transparent; }
.am-bar-box {
  background-image: linear-gradient(to bottom, #fafcfe, #cbd5df);
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
.am-tray-icon { padding: 3px 5px; min-width: 20px; }
.am-tray-icon.attention { background: alpha(@am_accent, .24); box-shadow: inset 0 -2px @am_accent; }
.am-tray-menu-item { background: transparent; border: none; color: @am_text; padding: 7px 10px; border-radius: 8px; }
.am-tray-menu-item:hover { background: alpha(@am_second, .15); }
.am-ai-chip {
  border-radius: 999px; padding: 2px 12px; font-size: 11px; font-weight: 800; letter-spacing: 1.5px;
  color: #e7edf3; background-image: linear-gradient(to right, @am_second, @am_accent);
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

/* Desktop surfaces use an opaque panel inside a transparent layer surface. */
window.am-overlay-clear { background: transparent; }
.am-popup-panel {
  background-image: linear-gradient(to bottom, #24233a, #0e0d17);
  border: 1px solid alpha(@am_second, .45); border-radius: 20px;
  color: @am_text; padding: 20px;
  box-shadow: 0 0 24px alpha(@am_accent, .16), inset 0 1px 0 alpha(white, .13);
}
button.am-picker-card { padding: 12px; background: alpha(white, .04); border: 1px solid alpha(white, .13); border-radius: 14px; color: @am_text; }
button.am-picker-card.selected { border: 2px solid @am_second; background: alpha(@am_second, .12); box-shadow: 0 0 16px alpha(@am_second, .22); }
button.am-picker-card:hover { background: alpha(white, .09); }
.am-pager-pill { padding: 2px 7px; border-radius: 7px; background: alpha(white,.05); color: @am_dim; }
.am-pager-pill.current { color: @am_second; border: 1px solid alpha(@am_second,.5); }

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

/* ---------- agent ---------- */
.am-agent-chip {
  border-radius: 999px; padding: 2px 12px; min-height: 18px; font-size: 11px; font-weight: 800; letter-spacing: 1.5px;
  color: #e7edf3; border: 1px solid alpha(white, .0);
  background-image: linear-gradient(to right, @am_accent, shade(@am_accent, .8));
  box-shadow: 0 0 14px alpha(@am_accent, .6);
}
.am-agent-chip.idle { color: @am_dim; background-image: none; background: alpha(white, .06); box-shadow: none; border-color: alpha(@am_second, .30); }
.am-agent-chip.idle:hover { border-color: @am_second; box-shadow: 0 0 10px alpha(@am_second, .5); }
.am-agent-chip.thinking { background-image: linear-gradient(to right, @am_second, shade(@am_second, .75)); box-shadow: 0 0 16px alpha(@am_second, .8); }
.am-agent-chip.tool { background-image: linear-gradient(to right, @am_second, @am_accent); box-shadow: 0 0 16px alpha(@am_accent, .7); }
.am-agent-chip.error { color: white; background-image: linear-gradient(to bottom, #ff4d4d, #9c1c1c); box-shadow: 0 0 14px alpha(#ff4d4d, .7); }
.am-agent-chip.paused { color: #ffb02e; background-image: none; background: alpha(#ffb02e, .12); border-color: alpha(#ffb02e, .6); box-shadow: none; }
.am-pill { border-radius: 999px; padding: 1px 10px; font-size: 10px; font-weight: 800; letter-spacing: 1.5px; }
.am-pill.on { color: #e7edf3; background-image: linear-gradient(to right, #39ff88, #19e3ff); box-shadow: 0 0 10px alpha(#39ff88, .55); }
.am-pill.off { color: @am_dim; background: alpha(white, .08); }
.am-pill.error { color: white; background: alpha(#ff4d4d, .55); border: 1px solid #ff4d4d; }
.am-keystate { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: @am_dim; }
.am-keystate.saved { color: #39ff88; text-shadow: 0 0 8px alpha(#39ff88, .55); }
.am-step { font-size: 10px; font-weight: 800; letter-spacing: 1.5px; color: @am_dim; padding: 3px 10px; border-radius: 999px; border: 1px solid alpha(white, .14); }
.am-step.active { color: white; border-color: @am_accent; background: alpha(@am_accent, .25); box-shadow: 0 0 10px alpha(@am_accent, .45); }
.am-step.done { color: @am_second; border-color: alpha(@am_second, .5); }
.am-agent-onboard { border-color: alpha(@am_second, .55); box-shadow: 0 0 22px alpha(@am_second, .22); }
.am-agent-missing { border-color: alpha(#ffb02e, .55); }
.am-agent-error { border-color: alpha(#ff4d4d, .6); }
.am-term { background: alpha(black, .55); color: #39ff88; font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; font-size: 12px; padding: 8px; }
.am-term text { background: transparent; color: #39ff88; }
window.am-agent-window { background: @am_bg; color: @am_text; }
.am-agent-frame { border: 1px solid alpha(@am_accent, .55); box-shadow: inset 0 0 28px alpha(@am_accent, .14), inset 0 0 0 1px alpha(@am_second, .25); }
.am-agent-header { background-image: linear-gradient(to bottom, #fafcfe, #cbd5df); border-bottom: 1px solid alpha(@am_accent, .55); box-shadow: 0 1px 14px alpha(@am_accent, .30); padding: 8px 14px; }
.am-agent-title { font-size: 13px; font-weight: 800; letter-spacing: 3px; color: @am_text; text-shadow: 0 0 12px alpha(@am_accent, .7); }
.am-agent-dot { min-width: 10px; min-height: 10px; border-radius: 999px; background: @am_dim; }
.am-agent-dot.idle { background: @am_second; box-shadow: 0 0 10px @am_second; }
.am-agent-dot.thinking, .am-agent-dot.tool { background: @am_accent; box-shadow: 0 0 12px @am_accent; }
.am-agent-dot.error { background: #ff4d4d; box-shadow: 0 0 12px #ff4d4d; }
.am-agent-dot.off { background: @am_dim; box-shadow: none; }
.am-agent-status { font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; font-size: 11px; letter-spacing: 1px; color: @am_dim; }
.am-agent-link { background: transparent; border: none; color: @am_second; font-weight: 700; padding: 4px 8px; }
.am-agent-link:hover { text-decoration: underline; }
.am-agent-banner { background: alpha(#ffb02e, .14); border-bottom: 1px solid alpha(#ffb02e, .5); padding: 6px 14px; color: #ffd48a; font-size: 12px; }
.am-agent-state { background-image: radial-gradient(circle at 50%% 40%%, alpha(@am_accent, .12), transparent 60%%); }
.am-agent-state-title { font-size: 20px; font-weight: 800; letter-spacing: 2px; }
.am-answer { background: alpha(black, .4); border: 1px solid alpha(@am_second, .35); border-radius: 14px; padding: 12px 14px; color: @am_text; font-size: 14px; }
.am-answer-meta { font-size: 10px; font-weight: 800; letter-spacing: 2px; color: @am_second; }
.am-risk { border-radius: 999px; padding: 2px 12px; font-size: 10px; font-weight: 800; letter-spacing: 2px; }
.am-risk.read { color: @am_dim; background: alpha(white, .08); }
.am-risk.act { color: #e7edf3; background: @am_second; box-shadow: 0 0 10px alpha(@am_second, .6); }
.am-risk.sensitive { color: #e7edf3; background: #ffb02e; box-shadow: 0 0 10px alpha(#ffb02e, .6); }
.am-risk.critical { color: white; background: #e0243a; box-shadow: 0 0 12px alpha(#ff4d4d, .8); }
.am-client { font-size: 11px; font-weight: 800; letter-spacing: 2px; color: @am_second; }

/* ---------- claude-os ---------- */
window.am-caster { background: alpha(#05040a, .84); }
.am-caster-title { font-size: 34px; font-weight: 800; letter-spacing: 14px; color: @am_text; text-shadow: 0 0 26px alpha(@am_accent, .8); }
.am-caster-sub { font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; font-size: 12px; letter-spacing: 5px; color: @am_second; }
.am-caster-hint { font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; font-size: 10px; letter-spacing: 2px; color: @am_dim; }
.am-caster-card {
  background-image: linear-gradient(to bottom, alpha(#2a2940, .95), alpha(#0d0c16, .97));
  border: 1px solid alpha(white, .18); border-radius: 28px; padding: 22px 26px 26px 26px; color: @am_text;
  box-shadow: 0 18px 60px alpha(black, .7), inset 0 1px 0 alpha(white, .16);
  transition: box-shadow 180ms ease-out, border-color 180ms ease-out;
}
.am-caster-card.focused {
  border: 2px solid @am_second;
  box-shadow: 0 0 46px alpha(@am_second, .55), 0 0 90px alpha(@am_accent, .30), 0 18px 60px alpha(black, .7), inset 0 1px 0 alpha(white, .22);
}
.am-caster-card.chatgpt.focused { border-color: @am_accent; box-shadow: 0 0 46px alpha(@am_accent, .55), 0 0 90px alpha(@am_second, .30), 0 18px 60px alpha(black, .7), inset 0 1px 0 alpha(white, .22); }
.am-caster-badge { font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; font-size: 12px; font-weight: 800; color: @am_dim; border: 1px solid alpha(white, .22); border-radius: 8px; padding: 1px 9px; }
.am-caster-card.focused .am-caster-badge { color: @am_text; border-color: @am_second; }
.am-caster-name { font-size: 26px; font-weight: 800; letter-spacing: 5px; }
.am-caster-action { font-size: 11px; font-weight: 800; letter-spacing: 3px; color: @am_dim; }
.am-caster-card.focused .am-caster-action { color: @am_second; text-shadow: 0 0 10px alpha(@am_second, .7); }

.am-chip { background: alpha(white, .05); border: 1px solid alpha(white, .14); border-radius: 999px; padding: 3px 14px; color: @am_dim; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; min-height: 0; }
.am-chip:hover { border-color: @am_second; color: @am_text; }
.am-chip.active { color: @am_text; border-color: @am_second; background: alpha(@am_second, .16); box-shadow: 0 0 10px alpha(@am_second, .4); }
.am-footer-btn { background: alpha(white, .05); border: 1px solid alpha(white, .14); border-radius: 12px; padding: 6px 14px; color: @am_text; font-weight: 700; font-size: 12px; }
.am-footer-btn:hover, .am-footer-btn:focus { border-color: @am_second; box-shadow: 0 0 12px alpha(@am_second, .4); }
.am-recent-label { font-size: 10px; font-weight: 700; letter-spacing: 2px; color: @am_dim; }
.am-bar-btn.flat-time { background-image: none; border-color: transparent; }
.am-bar-btn.flat-time:hover { border-color: @am_accent; }
.am-bar-btn.home { border-color: alpha(@am_accent, .55); }
.am-preview-bar { background-image: linear-gradient(to bottom, #fafcfe, #cbd5df); border: 1px solid alpha(@am_accent, .55); border-radius: 10px; padding: 4px 10px; min-height: 30px; }
.am-preview-chip { background: alpha(white, .08); border: 1px solid alpha(white, .16); border-radius: 999px; padding: 1px 10px; font-size: 10px; font-weight: 700; letter-spacing: 1px; color: @am_text; }
.am-claude-first { border-color: alpha(@am_second, .6); box-shadow: 0 0 24px alpha(@am_second, .22); }
.am-mode-card { background: alpha(white, .04); border: 1px solid alpha(white, .14); border-radius: 16px; padding: 14px; color: @am_text; }
.am-mode-card.selected { border: 2px solid @am_second; background: alpha(@am_second, .12); box-shadow: 0 0 16px alpha(@am_second, .25); }
'''


# Tesla-style look (ui_style = tesla): matte near-black surfaces, large rounded touch targets, flat solid controls, one calm
# accent, no neon glows. Loaded after CSS, so equal-specificity rules here win. Contains no percent signs on purpose.
TESLA_CSS = """
@define-color am_bg #0c0d10;
@define-color am_panel #17181c;
@define-color am_panel_hi #202228;
@define-color am_line #2a2c33;
@define-color am_text #f4f5f7;
@define-color am_dim #8b8f98;
@define-color am_accent #3e6ae1;
@define-color am_second #3e6ae1;
* { font-family: "Inter", "Noto Sans", sans-serif; }
.am-mono, .am-clock { font-family: "Inter", "Noto Sans", sans-serif; letter-spacing: 0; }
.am-label { letter-spacing: 1.5px; font-weight: 600; color: @am_dim; }

window.am-bar, window.am-bar > * { background: transparent; }
.am-bar-box { background: alpha(#0c0d10, .88); background-image: none; border-bottom: 1px solid alpha(white, .06); box-shadow: none; padding: 0 18px; min-height: 44px; }
.am-bar-btn { background: transparent; background-image: none; border: none; border-radius: 14px; padding: 4px 14px; min-height: 30px; font-size: 14px; font-weight: 600; letter-spacing: 0; color: @am_text; }
.am-bar-btn:hover { background: alpha(white, .08); box-shadow: none; border: none; }
.am-bar-btn.ai { border: none; }
.am-bar-btn.ai:hover { background: alpha(white, .10); box-shadow: none; }
.am-bar-btn.home { border: none; background: alpha(@am_accent, .20); }
.am-bar-btn.flat-time { background: transparent; }
.am-bar-icon { border-radius: 14px; padding: 5px 10px; }
.am-bar-icon:hover { background: alpha(white, .08); }
.am-clock { font-size: 20px; font-weight: 600; }
.am-appname { font-size: 14px; font-weight: 600; letter-spacing: 0; }
.am-ai-chip { background: alpha(white, .08); background-image: none; color: @am_text; box-shadow: none; letter-spacing: 0; font-weight: 600; padding: 4px 14px; }
.am-ai-chip.idle { background: alpha(white, .05); color: @am_dim; }
.am-ai-stop { background: #e82127; border: none; letter-spacing: 0; }

window.am-dock, window.am-dock > * { background: transparent; }
.am-dock-box { background: alpha(#17181c, .94); background-image: none; border: 1px solid alpha(white, .07); border-radius: 30px; padding: 10px 12px;
  box-shadow: 0 18px 50px alpha(black, .55); }
.am-dock-box.vertical { padding: 14px 10px; }
.am-dock-item { border-radius: 22px; padding: 8px; margin: 0; background: transparent; }
.am-dock-item:hover { background: alpha(white, .09); box-shadow: none; }
.am-dock-ai { background: alpha(@am_accent, .14); border: none; }
.am-dock-dot { background: @am_text; box-shadow: none; min-width: 5px; min-height: 5px; border-radius: 999px; margin-top: 2px; }
.am-dock-sep { background: alpha(white, .10); margin: 8px 6px; }
.am-dock-sep.vertical { min-height: 1px; min-width: 0; margin: 6px 10px; }

window.am-overlay { background: alpha(#050506, .78); }
.am-panel { background: #17181c; background-image: none; border: 1px solid alpha(white, .07); border-radius: 26px; box-shadow: 0 24px 70px alpha(black, .6); }
.am-search { background: #0c0d10; border: 1px solid alpha(white, .08); border-radius: 18px; padding: 12px 18px; font-size: 18px; box-shadow: none; }
.am-search:focus-within { border-color: @am_accent; box-shadow: none; }
.am-app { border-radius: 22px; border: 1px solid transparent; }
.am-app:hover, .am-app:focus { background: alpha(white, .07); border-color: transparent; }
.am-ask { background: alpha(@am_accent, .16); background-image: none; border: none; border-radius: 18px; }
.am-ask:hover { box-shadow: none; background: alpha(@am_accent, .26); }
.am-chip { border-radius: 999px; letter-spacing: 0; font-weight: 600; border: none; background: alpha(white, .07); }
.am-chip.active { background: @am_accent; color: white; box-shadow: none; border: none; }
.am-footer-btn { border-radius: 16px; border: none; background: alpha(white, .07); }
.am-footer-btn:hover, .am-footer-btn:focus { background: alpha(white, .12); box-shadow: none; }

window.am-caster { background: alpha(#050506, .88); }
.am-caster-title { text-shadow: none; letter-spacing: 6px; font-weight: 600; }
.am-caster-sub, .am-caster-hint { font-family: "Inter", "Noto Sans", sans-serif; letter-spacing: 1px; color: @am_dim; }
.am-caster-card { border-radius: 32px; background: #17181c; background-image: none; border: 1px solid alpha(white, .07); box-shadow: 0 18px 50px alpha(black, .5); }
.am-caster-card.focused, .am-caster-card.chatgpt.focused { border: 2px solid @am_accent; box-shadow: 0 0 0 6px alpha(@am_accent, .22), 0 24px 70px alpha(black, .6); }
.am-caster-name { letter-spacing: 1px; font-weight: 600; }
.am-caster-action { letter-spacing: 1px; font-weight: 600; }
.am-caster-card.focused .am-caster-action { color: @am_accent; text-shadow: none; }

.am-toast { background: #17181c; background-image: none; border: 1px solid alpha(white, .07); border-left: 3px solid @am_accent; border-radius: 22px; box-shadow: 0 14px 40px alpha(black, .55); }
.am-primary { background: @am_accent; background-image: none; border: none; border-radius: 16px; padding: 10px 22px; box-shadow: none; font-weight: 600; }
.am-secondary { background: alpha(white, .08); background-image: none; border: none; border-radius: 16px; padding: 10px 22px; font-weight: 600; }
.am-card { background: #17181c; background-image: none; border: 1px solid alpha(white, .06); border-radius: 22px; }
.am-heading { font-weight: 600; letter-spacing: 0; }
.am-sidebar { background: #111215; background-image: none; border-right: 1px solid alpha(white, .06); }
.am-side-item { border-radius: 16px; font-weight: 600; }
.am-side-item:checked, .am-side-item.active { background: alpha(@am_accent, .22); background-image: none; border-color: transparent; box-shadow: none; }
scale highlight { background: @am_accent; background-image: none; }
scale slider { box-shadow: none; }
switch:checked { background: @am_accent; background-image: none; }
entry:focus-within { border-color: @am_accent; }
.am-mode-card { border-radius: 22px; }
.am-mode-card.selected { border: 2px solid @am_accent; background: alpha(@am_accent, .14); box-shadow: none; }
.am-claude-first { border-color: alpha(@am_accent, .6); box-shadow: none; }
/* slick: motion and finish */
.am-dock-item, .am-bar-btn, .am-bar-icon, .am-chip, .am-footer-btn, .am-app, .am-ask, .am-secondary, .am-primary, .am-side-item { transition: background 180ms ease, transform 180ms ease, box-shadow 180ms ease, opacity 180ms ease; }
.am-dock-item:hover { transform: scale(1.08); }
.am-dock-item:active { transform: scale(0.96); background: alpha(white, .05); }
.am-app:hover { transform: translateY(-2px); }
.am-primary:hover { background: shade(@am_accent, 1.12); }
.am-secondary:hover { background: alpha(white, .13); }
.am-caster-card { transition: transform 240ms ease, box-shadow 240ms ease, border-color 240ms ease; }
.am-caster-card.focused { transform: scale(1.04); }
.am-clock { font-feature-settings: "tnum"; font-weight: 500; letter-spacing: -0.3px; }
.am-bar-box { box-shadow: 0 1px 0 alpha(white, .04), 0 8px 30px alpha(black, .35); }
.am-dock-box { border: 1px solid alpha(white, .09); box-shadow: inset 0 1px 0 alpha(white, .06), 0 20px 56px alpha(black, .6); }
.am-panel { box-shadow: inset 0 1px 0 alpha(white, .05), 0 28px 80px alpha(black, .65); }
"""


def apply(accent='#1764bd', secondary='#237dcc', style='retro'):
    """Install the CSS for the default display. Returns the provider so callers can reload it."""
    provider = Gtk.CssProvider()
    text = CSS % {'accent': accent, 'secondary': secondary}
    if style == 'tesla':
        text += TESLA_CSS
    provider.load_from_string(text)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    Gtk.Settings.get_default().set_property('gtk-application-prefer-dark-theme', True)
    try:  # the Tesla look has its own matte app icons (theme AmerikaTesla, falls back to AmerikaOS)
        Gtk.Settings.get_default().set_property('gtk-icon-theme-name', 'AmerikaTesla' if style == 'tesla' else 'AmerikaOS')
    except (TypeError, ValueError):
        pass
    return provider
