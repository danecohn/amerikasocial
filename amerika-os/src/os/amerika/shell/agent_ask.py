"""Launcher integration: an "Ask Amerika Agent" row and the answer panel (streamed from `amerika-agent ask`)."""
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk  # noqa: E402

from ..agent import cli, model
from . import apps

MAX_ANSWER = 8000


class AskPanel(Gtk.Box):
    """Sits under the search box. `update(text)` decides whether to show the row; `submit()` asks; `reset()` clears."""

    def __init__(self, shell):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.shell = shell
        self.question = None
        self.explicit = False
        self._handle = None
        self._lines = []
        self.row = Gtk.Button(halign=Gtk.Align.START)
        self.row.add_css_class('am-ask')
        inner = Gtk.Box(spacing=8)
        inner.append(apps.icon_image('amerika-ai', 22))
        self.row_label = Gtk.Label(label='Ask Amerika Agent')
        inner.append(self.row_label)
        self.row.set_child(inner)
        self.row.connect('clicked', lambda *_: self.submit())
        self.append(self.row)

        self.answer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.meta = Gtk.Label(label='', xalign=0)
        self.meta.add_css_class('am-answer-meta')
        self.answer = Gtk.Label(label='', xalign=0, yalign=0, wrap=True, selectable=True)
        self.answer.add_css_class('am-answer')
        self.scroller = Gtk.ScrolledWindow(min_content_height=60, max_content_height=240, propagate_natural_height=True)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_child(self.answer)
        self.answer_box.append(self.meta)
        self.answer_box.append(self.scroller)
        self.append(self.answer_box)
        self.reset()

    def reset(self):
        self.cancel()
        self.question, self.explicit = None, False
        self.row.set_visible(False)
        self.answer_box.set_visible(False)

    def cancel(self):
        if self._handle:
            self._handle.cancel()
            self._handle = None

    def update(self, text):
        """Called on every change of the launcher search text."""
        question, explicit = model.parse_ask(text)
        if self._handle is not None and question == self.question:
            return
        self.cancel()
        self.answer_box.set_visible(False)
        self.question, self.explicit = question, explicit
        self.row.set_visible(bool(question) or (explicit and bool((text or '').strip())))
        self.row_label.set_text(f'Ask Amerika Agent:  {question}' if question else 'Ask Amerika Agent  (type your question)')
        self.row.set_sensitive(bool(question))

    def submit(self):
        if not self.question:
            return False
        question = self.question
        self._lines = []
        self.answer_box.set_visible(True)
        self.meta.set_text('AMERIKA AGENT · THINKING…')
        self.answer.set_text('')
        if not cli.available():
            self.meta.set_text('AMERIKA AGENT')
            self.answer.set_text('Amerika Agent is not installed. Install the amerika-agent package (sudo apt install amerika-agent) and ask again.')
            return True
        self.cancel()
        self._handle = cli.AskHandle(question, lambda line: GLib.idle_add(self._line, line), lambda code, err: GLib.idle_add(self._done, code, err))
        return True

    def _line(self, line):
        self._lines.append(line)
        self.answer.set_text('\n'.join(self._lines)[-MAX_ANSWER:])
        self.meta.set_text('AMERIKA AGENT · ANSWERING…')
        return False

    def _done(self, code, err):
        self._handle = None
        if code == 0:
            self.meta.set_text('AMERIKA AGENT')
            if not self._lines:
                self.answer.set_text('The agent finished without an answer.')
        else:
            self.meta.set_text('AMERIKA AGENT · COULD NOT ANSWER')
            if not self._lines:
                self.answer.set_text(err or 'The agent did not answer. Open Settings > Amerika Agent to check that it is running and has an API key.')
        return False
