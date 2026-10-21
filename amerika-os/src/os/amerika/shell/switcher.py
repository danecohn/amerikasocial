"""Accessible window switcher and searchable overview, using KWin's window IDs."""
import gi
gi.require_version('Gtk','4.0')
gi.require_version('Gdk','4.0')
from gi.repository import Gdk, GObject, Gtk
from .. import deskconf
from . import dutil, layer, workspaces


def candidates(state,conf=None,app_only=False):
    conf=conf or {}
    windows=[w for w in state.get('windows',[]) if w.get('normal') and not w.get('skip')]
    active=next((w for w in windows if w.get('active')),None)
    if app_only and active:
        windows=[w for w in windows if dutil.app_key(w)==dutil.app_key(active)]
    if not conf.get('all_desktops',True):
        current=state.get('current',1)
        windows=[w for w in windows if w.get('allDesktops') or current in w.get('desktops',[])]
    if not conf.get('include_minimized',True):windows=[w for w in windows if not w.get('minimized')]
    order={ident:i for i,ident in enumerate(state.get('mru',[]))}
    windows.sort(key=lambda w:order.get(w['id'],1000-int(w.get('active',False))*100))
    if conf.get('group_apps'):
        seen=set();grouped=[]
        for w in windows:
            key=dutil.app_key(w)
            if key not in seen:grouped.append(w);seen.add(key)
        return grouped
    return windows


class WindowPicker(Gtk.Window):
    def __init__(self,shell,overview=False):
        super().__init__(application=shell,title='Window overview' if overview else 'Switch windows')
        self.shell,self.overview=shell,overview
        self.items=[];self.index=0;self.cards=[]
        self.add_css_class('am-overlay-clear')
        layer.setup(self,'overlay',keyboard='exclusive',namespace='amerika-overview' if overview else 'amerika-switcher')
        self.set_default_size(1050 if overview else 1000,700 if overview else 400)
        root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14)
        root.add_css_class('am-popup-panel')
        for side in ('top','bottom','start','end'):getattr(root,'set_margin_'+side)(20)
        self.set_child(root)
        root.append(dutil.label('WINDOW OVERVIEW' if overview else 'SWITCH WINDOWS','am-heading'))
        if overview:
            self.search=Gtk.SearchEntry(placeholder_text='Find a window…')
            self.search.connect('search-changed',lambda *_:self.render())
            self.search.connect('activate',lambda *_:self.commit())
            root.append(self.search)
            self.desktops=Gtk.Box(spacing=8);root.append(self.desktops)
        self.grid=Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,column_spacing=10,row_spacing=10,
                              max_children_per_line=3,min_children_per_line=3,homogeneous=True)
        scrolled=Gtk.ScrolledWindow(vexpand=True,hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC,Gtk.PolicyType.AUTOMATIC);scrolled.set_child(self.grid)
        root.append(scrolled)
        root.append(dutil.label('Click to activate · Enter to select · Escape to cancel' if overview else
                                'Keep holding Alt · Tab to choose · Release Alt to activate · Escape to cancel','am-sub'))
        controller=Gtk.EventControllerKey()
        controller.connect('key-pressed',self._key)
        controller.connect('key-released',self._released)
        self.add_controller(controller)
        self.connect('close-request',lambda *_:(self.hide(),True)[1])

    def open(self,step=1,app_only=False):
        if self.get_visible() and not self.overview:
            self.advance(step);return
        self.items=candidates(self.shell.windows.state,deskconf.get('switcher',self.shell.settings),app_only)
        if not self.items:return
        self.index=0 if self.overview else step%len(self.items)
        if self.overview:self.search.set_text('')
        self.render();self.present()
        if self.overview:self.search.grab_focus()

    def render(self):
        dutil.clear(self.grid);self.cards=[]
        if self.overview:
            dutil.clear(self.desktops)
            for d in workspaces.desktops_of(self.shell.windows.state):
                b=Gtk.Button(label=d['name']);b.add_css_class('am-secondary')
                b.connect('clicked',lambda _,n=d['n']:(self.hide(),self.shell.parity.desktops.switch_to(n)))
                self.desktops.append(b)
            add=Gtk.Button(label='+ Desktop')
            add.connect('clicked',lambda *_:self.shell.parity.desktops.create())
            self.desktops.append(add)
        query=self.search.get_text().casefold() if self.overview else ''
        for index,win in enumerate(self.items):
            if query and query not in (win.get('caption','')+' '+win.get('cls','')).casefold():continue
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
            box.append(dutil.window_icon(win,48))
            picture=Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN)
            picture.set_size_request(220 if self.overview else 160,120 if self.overview else 80)
            if deskconf.get('switcher.thumbnails',self.shell.settings):
                box.append(picture)
                stamp=(win.get('caption'),win.get('w'),win.get('h'))
                self.shell.parity.thumbnails.get(win['id'],stamp,lambda tex,pic=picture:pic.set_paintable(tex))
            title=dutil.label(win.get('caption') or win.get('cls') or 'Window',wrap=True)
            title.set_max_width_chars(25);title.set_lines(2);title.set_ellipsize(3);box.append(title)
            b=Gtk.Button();b.set_child(box);b.add_css_class('am-picker-card')
            if index==self.index:b.add_css_class('selected')
            b.connect('clicked',lambda _,wid=win['id']:self.activate_window(wid))
            right=Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
            right.connect('pressed',lambda _,n,x,y,w=win,button=b:workspaces.window_menu(self.shell,w,button))
            b.add_controller(right)
            drag=Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            drag.connect('prepare',lambda _,x,y,wid=win['id']:Gdk.ContentProvider.new_for_value('window:'+wid))
            b.add_controller(drag)
            self.grid.append(b);self.cards.append((index,b))
        if self.cards and self.index not in {i for i,b in self.cards}:
            self.index=self.cards[0][0]
            self.cards[0][1].add_css_class('selected')

    def advance(self,step):
        if not self.items:return
        self.index=(self.index+step)%len(self.items)
        for index,card in self.cards:
            if index==self.index:card.add_css_class('selected');card.grab_focus()
            else:card.remove_css_class('selected')

    def activate_window(self,wid):
        self.hide();self.shell.windows.command('activate',wid)

    def commit(self):
        if self.overview and not self.cards:return
        if self.items:self.activate_window(self.items[self.index]['id'])
        else:self.hide()

    def _released(self,controller,key,*_):
        if not self.overview and key in (Gdk.KEY_Alt_L,Gdk.KEY_Alt_R):self.commit()

    def _key(self,controller,key,keycode,state):
        if key==Gdk.KEY_Escape:self.hide();return True
        if key in (Gdk.KEY_Return,Gdk.KEY_KP_Enter):self.commit();return True
        if not self.overview and key in (Gdk.KEY_Tab,Gdk.KEY_ISO_Left_Tab):
            self.advance(-1 if state&Gdk.ModifierType.SHIFT_MASK else 1);return True
        return False
