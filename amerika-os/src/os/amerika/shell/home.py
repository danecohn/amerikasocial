"""Claude-first home mode: which AI app is the home view, its window classes, the mode presets (reversible) and the supervisor.

Pure logic only (no GTK), so the unit tests can drive it with a fake clock and fake processes.
"""
import copy

from . import barlayout

# key -> description of the home candidates. `classes` are the lower-case window classes / desktop-file names the KWin rules match.
# The ChatGPT desktop app is an Electron build whose package.json has no desktopName, so its Wayland app_id is not
# fixed by a .desktop StartupWMClass; the usual candidates are listed and the user can add one in settings['home_classes'].
APPS = {
    'claude': {'id': 'com.anthropic.Claude', 'name': 'Claude', 'exec': 'claude-desktop',
               'classes': ['com.anthropic.claude', 'claude']},
    'chatgpt': {'id': 'chatgpt', 'name': 'ChatGPT', 'exec': 'chatgpt',
                'classes': ['chatgpt', 'codex', 'openai-codex-electron']},
}
HOME_MODES = ('claude', 'chatgpt', 'off')
MODE_CHOICES = [('claude', 'Claude first'), ('chatgpt', 'ChatGPT first'), ('off', 'Classic desktop')]
SCALE_MIN, SCALE_MAX = 0.8, 2.0
SCALE_DEFAULTS = {'chatgpt': 1.25, 'claude': 1.0}
SCALE_FLAG = '--force-device-scale-factor'

# Settings keys that "Switch to Claude-first mode" changes; the previous values are snapshotted so one click restores them.
MANAGED_KEYS = ('home_mode', 'dock_enabled', 'copilot_app', 'bar_layout', 'bar_preset', 'dock_position', 'ui_style', 'dock_size')


def key_for_desktop_id(desktop_id):
    d = str(desktop_id or '').removesuffix('.desktop').lower()
    for key, app in APPS.items():
        if d == app['id'].lower():
            return key
    return None


def mode(settings):
    value = settings.get('home_mode', 'off')
    return value if value in HOME_MODES else 'off'


def home_key(settings):
    """'claude' / 'chatgpt' when a home app is configured, else None."""
    m = mode(settings)
    return m if m in APPS else None


def classes(settings, key):
    extra = (settings.get('home_classes') or {}).get(key) or []
    out = list(APPS[key]['classes'])
    out += [str(c).lower() for c in extra if isinstance(c, str) and c.strip()]
    return sorted(set(out))


def rules(settings):
    """What the KWin bridge needs: only the active home app's classes, empty (disabled) when home_mode is off."""
    key = home_key(settings)
    return {'enabled': bool(key), 'key': key, 'classes': classes(settings, key) if key else []}


def window_matches(win, settings, key):
    names = {str(win.get('cls', '')).lower(), str(win.get('desktopFile', '')).removesuffix('.desktop').lower()}
    names.discard('')
    return bool(names & set(classes(settings, key)))


def home_windows(windows, settings, key=None):
    key = key or home_key(settings)
    if not key:
        return []
    return [w for w in windows if w.get('normal', True) and window_matches(w, settings, key)]


# ---------------------------------------------------------------- text size
def text_scale(settings, key):
    raw = settings.get('ai_text_scale')
    value = raw.get(key) if isinstance(raw, dict) else None
    if value is None:
        value = SCALE_DEFAULTS.get(key, 1.0)
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = SCALE_DEFAULTS.get(key, 1.0)
    return max(SCALE_MIN, min(SCALE_MAX, round(value, 2)))


def scale_for_desktop_id(settings, desktop_id):
    """The scale to launch this desktop entry with, or None when it is not one of the AI apps or the scale is 1.0."""
    key = key_for_desktop_id(desktop_id)
    if not key:
        return None
    scale = text_scale(settings, key)
    return None if abs(scale - 1.0) < 0.005 else scale


# ---------------------------------------------------------------- mode presets (opt-in, reversible)
PRESETS = {
    'claude': {'home_mode': 'claude', 'dock_enabled': True, 'copilot_app': 'caster', 'bar_preset': 'home', 'dock_position': 'right',
               'ui_style': 'tesla', 'dock_size': 64},
    'chatgpt': {'home_mode': 'chatgpt', 'dock_enabled': True, 'copilot_app': 'caster', 'bar_preset': 'home', 'dock_position': 'right',
                'ui_style': 'tesla', 'dock_size': 64},
    'off': {'home_mode': 'off', 'dock_enabled': True, 'copilot_app': 'claude', 'bar_preset': 'classic', 'dock_position': 'bottom',
            'ui_style': 'retro', 'dock_size': 56},
}


def current_style(settings):
    """Which of the three styles the settings are in: 'claude', 'chatgpt' or 'off' (Classic)."""
    return mode(settings)


def snapshot(settings):
    """The managed values as they are now; absent keys are recorded as None so a revert removes them again."""
    return {k: copy.deepcopy(settings.get(k)) for k in MANAGED_KEYS}


def apply_style(settings, style):
    """Return a NEW settings dict with the preset applied. The first switch away from Classic stores a snapshot; switching
    between the Claude/ChatGPT styles keeps the original snapshot so Revert always returns to what the user had."""
    if style not in PRESETS:
        raise ValueError('style must be claude, chatgpt or off')
    out = copy.deepcopy(settings)
    if style != 'off' and not out.get('claude_first_snapshot'):
        out['claude_first_snapshot'] = snapshot(settings)
    preset = PRESETS[style]
    for k in ('home_mode', 'dock_enabled', 'copilot_app', 'dock_position', 'ui_style', 'dock_size'):
        out[k] = preset[k]
    out['bar_preset'] = preset['bar_preset']
    out['bar_layout'] = barlayout.preset(preset['bar_preset'])
    if style == 'off':
        # Classic: nothing to snapshot, and any older snapshot is no longer needed
        out.pop('claude_first_snapshot', None)
    out['claude_os_prompt'] = 'answered'
    return out


def revert(settings):
    """Return a NEW settings dict with the snapshot restored (None values remove the key), or None when no snapshot exists."""
    snap = settings.get('claude_first_snapshot')
    if not isinstance(snap, dict):
        return None
    out = copy.deepcopy(settings)
    for k in MANAGED_KEYS:
        if k not in snap:
            continue
        if snap[k] is None:
            out.pop(k, None)
        else:
            out[k] = copy.deepcopy(snap[k])
    out.pop('claude_first_snapshot', None)
    out['claude_os_prompt'] = 'answered'
    return out


# ---------------------------------------------------------------- supervisor
class HomeSupervisor:
    """Keeps the home app running. Decisions only: the caller provides the clock, `has_window()` and `launch()`.

    `tick()` is called every couple of seconds. A launch is expected to show a window within `startup_grace` seconds; if it
    does not, or the window disappears, the app is launched again after an exponentially growing delay (backoff). A run that
    stayed up for `stable_after` seconds resets the delay. After `max_failures` launches in a row that never produced a
    window the supervisor gives up (state 'gave-up') instead of looping forever.
    """

    def __init__(self, has_window, launch, clock, backoff=(2, 4, 8, 16, 30, 60), startup_grace=30, stable_after=60, max_failures=8,
                 on_give_up=None):
        self.has_window, self.launch, self.clock = has_window, launch, clock
        self.backoff, self.startup_grace, self.stable_after, self.max_failures = tuple(backoff), startup_grace, stable_after, max_failures
        self.on_give_up = on_give_up
        self.active = False
        self.state = 'stopped'          # stopped | starting | running | waiting | gave-up
        self.failures = 0
        self.launches = 0
        self._launched_at = None
        self._seen_at = None
        self._retry_at = None
        self._paused_until = 0.0

    # ----- control
    def start(self, launch_now=True):
        self.active = True
        self.failures = 0
        self._paused_until = 0.0
        self._retry_at = None
        self._seen_at = None
        self._launched_at = None
        self.state = 'starting'
        if launch_now:
            if self.has_window():
                self._seen_at = self.clock()
                self.state = 'running'
            else:
                self._do_launch()

    def stop(self):
        self.active = False
        self.state = 'stopped'
        self._retry_at = None

    def pause(self, seconds):
        """Do not relaunch for a while (the app is being restarted on purpose, e.g. after a text size change)."""
        self._paused_until = self.clock() + seconds
        self._seen_at = None
        self._launched_at = None
        if self.active:
            self.state = 'waiting'

    # ----- driving
    def _do_launch(self):
        self.launches += 1
        self._launched_at = self.clock()
        self._seen_at = None
        self._retry_at = None
        self.state = 'starting'
        self.launch()

    def _delay(self):
        return self.backoff[min(max(self.failures - 1, 0), len(self.backoff) - 1)]

    def tick(self):
        if not self.active or self.state == 'gave-up':
            return self.state
        now = self.clock()
        if now < self._paused_until:
            return self.state
        if self.has_window():
            if self._seen_at is None:
                self._seen_at = now
            self.state = 'running'
            if now - self._seen_at >= self.stable_after:
                self.failures = 0
            self._launched_at = self._launched_at if self._launched_at is not None else now
            self._retry_at = None
            return self.state
        # no window
        if self._seen_at is not None:                 # it was there and has gone: closed or crashed
            ran = now - self._seen_at
            self._seen_at = None
            if ran >= self.stable_after:
                self.failures = 0
            self.failures += 1
            self._schedule_retry(now)
        elif self._retry_at is None and (self._launched_at is None or now - self._launched_at >= self.startup_grace):
            self.failures += 1                        # launched but never produced a window
            self._schedule_retry(now)
        if self._retry_at is not None and now >= self._retry_at:
            if self.failures >= self.max_failures:
                self.state = 'gave-up'
                self.active = False
                if self.on_give_up:
                    self.on_give_up()
                return self.state
            self._do_launch()
        return self.state

    def _schedule_retry(self, now):
        self._retry_at = now + self._delay()
        self.state = 'waiting'
