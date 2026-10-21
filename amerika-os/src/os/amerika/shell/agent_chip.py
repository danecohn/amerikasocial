"""The bar chip that shows what Amerika Agent is doing. Click opens the Agent window."""
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa: E402

STATES = ('idle', 'thinking', 'tool', 'error', 'paused')


class AgentChip(Gtk.Button):
    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        self.add_css_class('am-agent-chip')
        self.add_css_class('idle')
        self._label = Gtk.Label(label='AGENT · IDLE')
        self._label.set_ellipsize(3)
        self._label.set_max_width_chars(34)
        self.set_child(self._label)
        self.set_visible(False)
        self.set_tooltip_text('Open Amerika Agent')
        self.connect('clicked', lambda *_: shell.agent.open_window())
        shell.agent.connect('changed', lambda *_: self.refresh())
        self.refresh()

    def refresh(self):
        label, state, visible = self.shell.agent.chip()
        self._label.set_text(label)
        for s in STATES:
            self.remove_css_class(s)
        self.add_css_class(state)
        self.set_visible(visible)
