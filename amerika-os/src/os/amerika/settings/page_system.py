"""Native settings pages built on the bounded, unprivileged system backends.

Reads and writes run on workers. Opening a page never changes a setting.
Privileged actions go through their fixed polkit helpers after a confirmation.
"""
from gi.repository import Gtk
from . import ui
from .. import (accessibility, accounts, bluetooth, datetime_, defaults, inputdev, language,
                notifprefs, printers, privacy, sharing, shortcuts, storage, updates)


class Page:
    def __init__(self,app,title,intro,fetch,render):
        self.app,self.fetch,self.render=app,fetch,render
        self.widget=ui.page(title,intro)
        self.widget.controller=self
        self.message=ui.status_label()
        self.widget.append(ui.row('Status',control=ui.button('Refresh',self.load)))
        self.widget.append(self.message)
        self.body=ui.list_box();self.widget.append(self.body)
        self.loaded=False;self.busy=False;self.notice=''
        self.load()

    def load(self):
        if self.busy:return
        self.loaded=False;self.busy=True
        self.body.set_sensitive(False);self.message.set_text('Reading settings…')
        def done(result):
            self.busy=False;self.loaded=True
            ui.clear(self.body);self.body.set_sensitive(True)
            if result is None:
                self.message.set_text('Settings could not be read. Check that the system service is available.')
            else:
                try:self.render(self,result);self.message.set_text(self.notice);self.notice=''
                except (KeyError,TypeError,ValueError):
                    self.message.set_text('The system service returned an unsupported response.')
        ui.async_call(self.fetch,done)

    def apply(self,fn,accept_false=False):
        if self.busy:return
        self.busy=True;self.body.set_sensitive(False);self.message.set_text('Applying…')
        def work():
            try:
                result=fn()
                if (result is False and not accept_false) or (isinstance(result,dict) and result.get('ok') is False):
                    return False,'The change was not applied. It may have been cancelled or the service is unavailable.'
                return True,''
            except ValueError as error:return False,str(error)[:250]
            except Exception:return False,'The change could not be applied. Check the system service and try again.'
        def done(result):
            self.busy=False;self.body.set_sensitive(True)
            if result and result[0]:self.load()
            else:self.message.set_text(result[1] if result else 'The change failed.')
        ui.async_call(work,done)

    def action(self,text,fn,question=None):
        def clicked():
            if question:ui.confirm(self.app.win,text,question,lambda:self.apply(fn),yes_label=text)
            else:self.apply(fn)
        return ui.button(text,clicked)

    def toggle(self,title,value,fn,sub=None,returns_value=False):
        return ui.switch_row(title,sub,value,lambda on:self.apply(lambda:fn(on),accept_false=returns_value))

    def choose(self,title,options,value,fn,sub=None):
        return ui.dropdown_row(title,sub,options,value,lambda v:self.apply(lambda:fn(v)))

    def field(self,title,value,fn,sub=None):
        entry=ui.entry(str(value or ''))
        controls=Gtk.Box(spacing=6);controls.append(entry)
        controls.append(self.action('Apply',lambda:fn(entry.get_text())))
        return ui.row(title,sub,controls)

    def section(self,title,*rows,note=None):self.body.append(ui.section(title,*rows,note=note))


def build_bluetooth(app):
    def fetch():return bluetooth.adapter(),bluetooth.devices()
    def render(p,data):
        adapter,devices=data
        if not adapter:p.section('Bluetooth',ui.empty_state('No Bluetooth adapter is available.'));return
        p.section('Adapter',p.toggle('Bluetooth',adapter.get('powered'),bluetooth.set_power),
                  p.toggle('Discoverable',adapter.get('discoverable'),bluetooth.set_discoverable,
                           'Other devices can find this computer while this is on.'),
                  ui.row('Find devices',control=p.action('Scan',lambda:bluetooth.scan(True))),
                  ui.row('Stop discovery',control=p.action('Stop scanning',lambda:bluetooth.scan(False))))
        for d in devices:
            controls=Gtk.Box(spacing=6);mac=d['address']
            if d['paired']:
                fn=bluetooth.disconnect if d['connected'] else bluetooth.connect
                controls.append(p.action('Disconnect' if d['connected'] else 'Connect',lambda fn=fn,mac=mac:fn(mac)))
                controls.append(p.action('Forget',lambda mac=mac:bluetooth.forget(mac),'Remove this pairing?'))
            else:controls.append(p.action('Pair',lambda mac=mac:bluetooth.pair(mac),
                    'Pair with this device? Built-in pairing supports devices without a PIN. Use the system Bluetooth pairing application for keyboards that require a code.'))
            detail=('Connected' if d['connected'] else ('Paired' if d['paired'] else 'Available'))
            if d.get('battery') is not None:detail+=f' · Battery {d["battery"]}%'
            p.section(d['name'],ui.row(mac,detail,controls))
        if not devices:p.section('Devices',ui.empty_state('No devices found. Put a device in pairing mode, scan, then refresh.'))
    return Page(app,'Bluetooth','Manage nearby devices and saved pairings.',fetch,render).widget


def build_sharing(app):
    def render(p,data):
        for service in data:
            detail='Running' if service['active'] else ('Stopped' if service['installed'] else 'Not installed')
            if service['toggle']:
                row=p.toggle(service['name'],service['active'],lambda on,u=service['unit']:sharing.set_user_service(u,on),
                             'Allow access only from people and networks you trust.')
            else:row=ui.row(service['name'],detail+((' · '+service['how']) if service.get('how') else ''))
            p.section('Service',row)
    return Page(app,'Sharing & remote desktop','Review services that expose this computer to other devices.',sharing.status,render).widget


def build_input(app):
    def fetch():return {'layouts':inputdev.layouts(),'available':inputdev.available_layouts()[0],
                        'repeat':inputdev.repeat(),'compose':inputdev.compose_key(),'switch':inputdev.switch_shortcut(),
                        'copilot':inputdev.copilot_get(),'devices':inputdev.pointing_devices()}
    def render(p,d):
        rows=[]
        for i,item in enumerate(d['layouts']):
            controls=Gtk.Box(spacing=5)
            if i:controls.append(p.action('Move up',lambda i=i:inputdev.move_layout(i,-1)))
            if len(d['layouts'])>1:controls.append(p.action('Remove',lambda i=i:inputdev.remove_layout(i)))
            rows.append(ui.row(item['layout']+(' · '+item['variant'] if item['variant'] else ''),control=controls))
        options=[('', 'Choose a layout…')]+d['available']
        rows.append(p.choose('Add a layout',options,'',lambda code:inputdev.add_layout(code) if code else True))
        rows.append(p.choose('Layout shortcut',inputdev.SWITCH_OPTIONS,d['switch'],inputdev.set_switch_shortcut))
        rows.append(p.choose('Compose key',inputdev.COMPOSE_OPTIONS,d['compose'],inputdev.set_compose_key))
        p.section('Keyboard',*rows)
        p.section('Repeat',p.field('Delay (milliseconds)',d['repeat']['delay'],lambda v:inputdev.set_repeat(delay=int(v))),
                  p.field('Rate (per second)',d['repeat']['rate'],lambda v:inputdev.set_repeat(rate=int(v))))
        p.section('Assistant',p.choose('Copilot key',inputdev.COPILOT_CHOICES,d['copilot'],inputdev.copilot_set))
        for dev in d['devices']:
            rows=[]
            for prop,title in [('tapToClick','Tap to click'),('naturalScroll','Natural scrolling'),
                               ('leftHanded','Left handed'),('disableWhileTyping','Disable while typing')]:
                if prop in dev['props'] and dev.get('supported',{}).get(prop) is not False:
                    rows.append(p.toggle(title,dev['props'][prop],lambda v,dev=dev,prop=prop:inputdev.set_device(dev,prop,v)))
            if 'pointerAcceleration' in dev['props']:
                rows.append(p.field('Pointer speed (−1 to 1)',dev['props']['pointerAcceleration'],
                                    lambda v,dev=dev:inputdev.set_device(dev,'pointerAcceleration',float(v))))
            p.section(dev['name'],*rows)
        if not d['devices']:p.section('Pointing devices',ui.empty_state('No configurable pointing devices were reported by KWin.'))
    return Page(app,'Keyboard & mouse','Keyboard layouts, assistant key and pointing devices.',fetch,render).widget


def build_shortcuts(app):
    def render(p,data):
        for item in data:
            p.section(item['title'],p.field('Shortcut',item['current'],lambda v,k=item['id']:shortcuts.set_shortcut(k,v),
                                           item.get('description')),
                      ui.row('Default: '+(item['default'] or 'None'),control=p.action('Reset',lambda k=item['id']:shortcuts.reset(k))))
    return Page(app,'Shortcuts','Type a key combination such as Meta+Shift+S. Conflicting shortcuts are rejected.',shortcuts.listing,render).widget


def build_notifications(app):
    def fetch():return notifprefs.load(),notifprefs.known_apps()
    def render(p,data):
        cfg,names=data
        p.section('Do not disturb',p.toggle('Do not disturb',cfg['dnd'],notifprefs.set_dnd,returns_value=True),
                  p.toggle('Allow urgent notifications',cfg['allow_urgent'],lambda v:notifprefs.set_option('allow_urgent',v),returns_value=True),
                  p.toggle('Quiet hours',cfg['schedule']['enabled'],lambda v:notifprefs.set_schedule(enabled=v)),
                  p.field('From (24-hour time)',cfg['schedule']['from'],lambda v:notifprefs.set_schedule(start=v)),
                  p.field('Until (24-hour time)',cfg['schedule']['to'],lambda v:notifprefs.set_schedule(end=v)))
        for name in names:
            rule=cfg['apps'].get(name,{})
            p.section(name,p.toggle('Notifications',rule.get('enabled',True),lambda v,n=name:notifprefs.set_app(n,enabled=v)),
                      p.toggle('Banners',rule.get('banners',True),lambda v,n=name:notifprefs.set_app(n,banners=v)))
    return Page(app,'Notifications','Quiet hours and controls for apps that have sent notifications.',fetch,render).widget


def build_accessibility(app):
    def render(p,d):
        p.section('Display',p.choose('Text size',accessibility.TEXT_SCALES,d['text_scale'],accessibility.set_text_scale),
                  p.toggle('High contrast',d['high_contrast'],accessibility.set_high_contrast,returns_value=True),
                  p.toggle('Reduce motion',d['reduce_motion'],accessibility.set_reduce_motion,returns_value=True),
                  p.toggle('Magnifier',d['zoom'],accessibility.set_zoom,returns_value=True))
        p.section('Keyboard',p.toggle('Sticky keys',d['sticky_keys'],lambda v:accessibility.set_keys(sticky=v)),
                  p.toggle('Slow keys',d['slow_keys'],lambda v:accessibility.set_keys(slow=v)),
                  p.toggle('Bounce keys',d['bounce_keys'],lambda v:accessibility.set_keys(bounce=v)),
                  note='Keyboard aids require the KDE accessibility service (kaccess) in this session.')
        reader=p.toggle('Screen reader',d['screen_reader'],accessibility.set_screen_reader,
                        'Orca' if d['orca_installed'] else 'Install Orca to enable the screen reader.')
        reader.set_sensitive(d['orca_installed']);p.section('Speech',reader)
    return Page(app,'Accessibility','Changes apply to supporting applications; some need to be reopened.',accessibility.state,render).widget


def build_datetime(app):
    def fetch():return datetime_.status(),datetime_.timezones()
    def render(p,data):
        d,zones=data
        if not d['available']:p.section('Time service',ui.empty_state('The system time service is unavailable.'));return
        p.section('Clock',p.toggle('24-hour clock',d['clock_24h'],datetime_.set_24h,returns_value=True),
                  p.toggle('Automatic time',d['ntp'],datetime_.set_ntp,
                           'Synchronized' if d['synchronized'] else 'Not synchronized'),
                  p.choose('Time zone',[(z,z) for z in zones],d['timezone'],datetime_.set_timezone))
        if not d['ntp']:p.section('Manual time',p.field('Date and time','',datetime_.set_time,'YYYY-MM-DD HH:MM:SS; authorization may be required.'))
    return Page(app,'Date & time','Set the clock and time zone. System changes use the standard authorization service.',fetch,render).widget


def build_language(app):
    def fetch():return language.user_settings(),language.installed()
    def render(p,data):
        d,locales=data;opts=[(v,language.describe(v)) for v in locales]
        if not opts:p.section('Locales',ui.empty_state('No UTF-8 locales are installed.'));return
        p.section('Language',p.choose('Display language',opts,d.get('lang'),language.set_language),note='Applies at your next login.')
        p.section('Regional formats',*[p.choose(title,[('', 'Use language default')]+opts,d.get(key,''),
                   lambda v,key=key:language.set_format(key,v) if v else language.clear_format(key))
                   for key,title in language.FORMAT_KEYS])
    return Page(app,'Language & region','Choose from the locales installed on this computer.',fetch,render).widget


def build_defaults(app):
    def fetch():return defaults.roles(),defaults.autostart_entries()
    def render(p,data):
        roles,startup=data
        for role in roles:
            if role['options']:p.section(role['name'],p.choose('Open with',role['options'],role['default'],
                          lambda v,k=role['id']:defaults.set_role(k,v)))
            else:p.section(role['name'],ui.empty_state('No compatible application is installed.'))
        p.section('Startup applications',*[p.toggle(e['name'],e['enabled'],lambda v,k=e['file']:defaults.set_autostart_enabled(k,v),e.get('comment'))
                                          for e in startup],note='Startup programs run at your next login.')
    return Page(app,'Default apps & startup','Choose applications for common file types and control login items.',fetch,render).widget


def build_users(app):
    def render(p,d):
        p.section('Your account',ui.row(d['username'],'Administrator' if d['admin'] else 'Standard account'),
                  p.field('Display name',d['real_name'],accounts.set_real_name),
                  ui.row('Password','Type your password directly in the system terminal.',p.action('Change password',accounts.change_password)))
    return Page(app,'Users','Manage the signed-in account. Passwords never pass through Amerika Settings.',accounts.current,render).widget


def build_privacy(app):
    def fetch():return {'permissions':privacy.all_permissions(),'recent':privacy.recent_enabled(),
                        'firewall':privacy.firewall_enabled(),'ufw':privacy.firewall_installed()}
    def render(p,d):
        p.section('Recent files',p.toggle('Remember recent files',d['recent'],privacy.set_recent_enabled,returns_value=True),
                  ui.row('Recent-file history',control=p.action('Clear history',privacy.clear_recent,'Forget the recent-file list? Your files are kept.')))
        firewall=p.toggle('Firewall',d['firewall'] is True,privacy.set_firewall,'Requires administrator authorization.')
        firewall.set_sensitive(d['ufw']);p.section('Network protection',firewall,
                            note=None if d['ufw'] else 'The UFW firewall is not installed.')
        for resource in d['permissions']:
            rows=[p.choose(appid,[(v,v.capitalize()) for v in privacy.VALUES],value,
                        lambda v,r=resource,a=appid:privacy.set_permission(r['table'],r['resource'],a,v))
                  for appid,value in resource['apps'].items()]
            p.section(resource['title'],*(rows or [ui.empty_state('No stored portal permissions.')]))
    return Page(app,'Privacy & security','Portal permissions apply to apps using desktop portals. Other applications may have direct device access.',fetch,render).widget


def build_printers(app):
    def fetch():return printers.available(),printers.printers(),printers.jobs()
    def render(p,data):
        available,queues,jobs=data
        if not available:p.section('Printers',ui.empty_state('CUPS printing tools are not installed.'));return
        for q in queues:
            name=q['name'];controls=Gtk.Box(spacing=6)
            controls.append(p.action('Make default',lambda n=name:printers.set_default(n)))
            controls.append(p.action('Print test page',lambda n=name:printers.test_page(n),'Print a test page on this printer?'))
            p.section(name,ui.row('Default printer' if q.get('default') else 'Printer',q.get('state',''),controls))
        if not queues:p.section('Printers',ui.empty_state('No printers are configured.'))
        for job in jobs:p.section('Print job',ui.row(str(job.get('id','')),str(job.get('queue',''))))
    return Page(app,'Printers','Configured CUPS printers and the current print queue.',fetch,render).widget


def build_storage(app):
    def fetch():return storage.volumes(),storage.home_usage()
    def render(p,data):
        volumes,folders=data
        for v in volumes:
            p.section(v['mount'],ui.row(v['device'],f'{storage.human(v["used"])} used · {storage.human(v["free"])} available'))
            bar=Gtk.ProgressBar();bar.set_fraction(max(0,min(1,v['percent']/100)));p.body.append(bar)
        p.section('Home folders',*[ui.row(f['name'],storage.human(f['bytes'])) for f in folders],
                  note='Usage is measured without deleting files or clearing caches.')
    return Page(app,'Storage','Mounted filesystems and space used by your home folders.',fetch,render).widget


def build_updates(app):
    def render(p,d):
        p.section('Software updates',ui.row(f'{d["count"]} available',f'{d["security"]} security updates · Last refreshed {updates.ago(d["last_refresh"])}'),
                  ui.row('Package information',control=p.action('Check for updates',updates.refresh_system)),
                  ui.row('System packages',control=p.action('Install updates',updates.upgrade_system,
                        'Install available Ubuntu and Amerika updates? Administrator authorization is required. Packages will not be removed. Display-manager upgrades are deferred so they cannot restart this desktop session.')))
        if d['reboot_required']:p.section('Restart required',ui.empty_state('Restart when you are ready to finish applying updates.'))
        for package in d['upgradable']:p.body.append(ui.row(package['name'],f'{package["old"]} → {package["new"]}'))
    return Page(app,'Updates','Updates come from your configured signed APT repositories.',updates.status,render).widget


def build_network(app):
    from .. import netman
    def fetch():return netman.status(),netman.wifi_list(),netman.connections(),netman.wired()
    def render(p,data):
        status,networks,profiles,wired=data
        if not status['available']:p.section('Network',ui.empty_state('NetworkManager is unavailable.'));return
        p.section('Radios',p.toggle('Airplane mode',status['airplane'],netman.set_airplane,returns_value=True),
                  p.toggle('Wi-Fi',status['wifi_enabled'],netman.set_wifi,returns_value=True),
                  ui.row('Nearby networks',control=p.action('Scan',netman.scan)))
        def join(net):
            ssid=net['ssid']
            if net['kind']=='enterprise':
                from .. import sysutil
                sysutil.popen(['nm-connection-editor']);return
            if net['saved'] or not net['secured']:p.apply(lambda:netman.join(ssid,kind=net['kind']));return
            ui.password_dialog(app.win,'Connect to '+ssid,'The password goes directly to NetworkManager.',
                               lambda password:p.apply(lambda:netman.join(ssid,password,kind=net['kind'])))
        for net in networks:
            p.section(net['ssid'],ui.row('Connected' if net['connected'] else net['security'] or 'Open network',
                      f'Signal {net["signal"]}%',None if net['connected'] else ui.button('Configure' if net['kind']=='enterprise' else 'Connect',lambda net=net:join(net))))
        for profile in profiles:
            uid=profile['uuid'];controls=Gtk.Box(spacing=6)
            fn=netman.disconnect if profile['active'] else netman.connect_saved
            controls.append(p.action('Disconnect' if profile['active'] else 'Connect',lambda uid=uid,fn=fn:fn(uid)))
            controls.append(p.action('Forget',lambda uid=uid:netman.forget(uid),'Forget this saved network profile and its stored credentials?'))
            p.section(profile['name'],ui.row(profile['type'],control=controls),
                      p.toggle('Connect automatically',profile['autoconnect'],lambda on,uid=uid:netman.set_autoconnect(uid,on)))
        for device in wired:p.section(device['device'],ui.row(device.get('connection') or 'Wired network',device.get('ip')))
        from .. import sysutil
        p.section('Advanced networking',ui.row('VPN, hidden networks, DNS and proxy',
                  'Open NetworkManager’s profile editor for advanced connection settings.',ui.button('Connection editor',lambda:sysutil.popen(['nm-connection-editor']))))
    return Page(app,'Network','Wi-Fi and saved connections. Wi-Fi passwords are passed on a private D-Bus call or stdin.',fetch,render).widget


def build_sound(app):
    from .. import audio
    def fetch():return audio.devices('output'),audio.devices('input'),audio.apps(),audio.cards()
    def render(p,data):
        outputs,inputs,apps,cards=data
        for kind,devices in (('output',outputs),('input',inputs)):
            if not devices:p.section(kind.capitalize(),ui.empty_state('No audio devices were reported.'))
            for device in devices:
                name=device['name']
                rows=[ui.row('Default '+kind if device['default'] else kind.capitalize(),control=None if device['default'] else
                            p.action('Use by default',lambda k=kind,n=name:audio.set_default(k,n))),
                      p.field('Volume (0–150%)',device['volume'],lambda v,k=kind,n=name:audio.set_volume(k,n,int(v))),
                      p.toggle('Mute',device['muted'],lambda v,k=kind,n=name:audio.set_mute(k,n,v))]
                if device['ports']:
                    rows.append(p.choose('Port',[(port['name'],port['description']) for port in device['ports'] if port['available']],
                                         device['active_port'],lambda v,k=kind,n=name:audio.set_port(k,n,v)))
                if kind=='output':rows.append(ui.row('Speakers',control=p.action('Test tone',lambda n=name:audio.test_tone(n))))
                p.section(device['description'],*rows)
        for stream in apps:p.section(stream['name'],p.field('App volume (0–150%)',stream['volume'],
                         lambda v,i=stream['index']:audio.set_app_volume(i,int(v))),
                         p.toggle('Mute app',stream['muted'],lambda v,i=stream['index']:audio.set_app_mute(i,v)))
        for card in cards:
            options=[(profile['name'],profile['description']) for profile in card['profiles'] if profile['available']]
            if options:p.section(card['description'],p.choose('Hardware profile',options,card['active_profile'],lambda v,n=card['name']:audio.set_profile(n,v)))
    return Page(app,'Sound','Outputs, microphones, per-app volume and hardware profiles.',fetch,render).widget


def build_power(app):
    from .. import powermgmt,sysutil
    def fetch():
        running=sysutil.run(['busctl','--user','list','--no-pager']).out
        return powermgmt.battery(),powermgmt.profiles(),powermgmt.threshold(),('org.kde.Solid.PowerManagement' in running)
    def render(p,data):
        battery,profiles,threshold,policy_service=data
        if battery:p.section('Battery',ui.row(f'{battery["percent"]}% · {battery["state"]}',
                           'Health '+str(battery['health'])+'%' if battery.get('health') is not None else None))
        if profiles['available']:p.section('Energy',p.choose('Power profile',[(n,t) for n,t in powermgmt.PROFILES if n in profiles['available']],
                                     profiles['current'],powermgmt.set_profile))
        if threshold['supported']:p.section('Battery care',p.field('Charge limit (50–100%)',threshold['value'],
                            lambda v:powermgmt.set_threshold(int(v)),'Administrator authorization is required.'))
        if not policy_service:p.section('Lid and idle policy',ui.empty_state('The power management service is not running in this session.'))
        else:
            for source,title in (('AC','On external power'),('Battery','On battery')):
                options=powermgmt.power_options(source)
                p.section(title,p.choose('Closing the lid',powermgmt.ACTIONS,options['lid_action'],
                                         lambda v,s=source:powermgmt.set_power_options(s,lid_action=v)),
                          p.choose('When idle',powermgmt.ACTIONS,options['idle_action'],lambda v,s=source:powermgmt.set_power_options(s,idle_action=v)),
                          p.field('Idle timeout (minutes)',options['idle_minutes'],lambda v,s=source:powermgmt.set_power_options(s,idle_minutes=int(v))))
    return Page(app,'Power','Battery information, supported charge limits and active power policies.',fetch,render).widget
