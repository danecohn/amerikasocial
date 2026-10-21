"""Explicit demo data for the private screenshot rig; no real service mutations."""
from .. import (accessibility, accounts, bluetooth, datetime_, defaults, inputdev, language,
                notifprefs, printers, privacy, sharing, shortcuts, storage, sysutil, updates)


def install():
    from .. import audio,displays,netman,powermgmt
    displays.outputs=lambda:[{'name':'eDP-1','enabled':True,'scale':1.5,'rotation':'normal','x':0,'y':0,
                             'mode':{'id':'1'},'modes':[{'id':'1','width':2880,'height':1920,'refresh':120}]}]
    displays.night_light=lambda:{'available':True,'active':False,'mode':'Automatic','night_temp':4500}
    netman.status=lambda:{'available':True,'airplane':False,'wifi_enabled':True}
    netman.wifi_list=lambda:[{'ssid':'Amerika Studio','kind':'wpa','security':'WPA2','secured':True,'saved':True,'connected':True,'signal':92},
                            {'ssid':'Guest','kind':'wpa','security':'WPA2','secured':True,'saved':False,'connected':False,'signal':66}]
    netman.connections=lambda:[{'name':'Amerika Studio','uuid':'00000000-0000-0000-0000-000000000001','type':'802-11-wireless',
                               'active':True,'autoconnect':True}]
    netman.wired=lambda:[]
    audio.devices=lambda kind:[{'name':'studio-'+kind,'description':'Speakers' if kind=='output' else 'Microphone',
                                'default':True,'volume':45,'muted':False,'ports':[],'active_port':None}]
    audio.apps=lambda:[{'name':'Amerika Venture','index':7,'volume':70,'muted':False}]
    audio.cards=lambda:[]
    powermgmt.battery=lambda:{'percent':82,'state':'discharging','health':97}
    powermgmt.profiles=lambda:{'available':['power-saver','balanced','performance'],'current':'balanced'}
    powermgmt.threshold=lambda:{'supported':True,'value':85}
    # All system-backend commands are inert, even if a test clicks a control.
    sysutil.set_runner(lambda *a,**k:sysutil.Result(1,'','Test fixture: no system service'),which=lambda _:None)
    sysutil.popen=lambda argv:None
    bluetooth.adapter=lambda:{'powered':True,'discoverable':False,'name':'Amerika laptop'}
    bluetooth.devices=lambda:[{'name':'Studio headphones','address':'00:11:22:33:44:55','paired':True,'connected':True,'battery':78},
                              {'name':'Wireless mouse','address':'00:11:22:33:44:56','paired':False,'connected':False,'battery':None}]
    sharing.status=lambda:[{'name':'Remote desktop','active':False,'installed':False,'toggle':False,'how':None},
                           {'name':'Remote login (SSH)','active':False,'installed':True,'toggle':False,'how':'Disabled'}]
    inputdev.layouts=lambda:[{'layout':'us','variant':''},{'layout':'fr','variant':''}]
    inputdev.available_layouts=lambda:([('us','English (US)'),('fr','French')],{})
    inputdev.pointing_devices=lambda:[{'name':'Surface Touchpad','sysname':'event1','kind':'touchpad','props':
                                      {'tapToClick':True,'naturalScroll':True,'pointerAcceleration':0.1},'supported':{}}]
    shortcuts.listing=lambda:[{'id':'Amerika: Launcher','title':'Launcher','description':'Open the launcher','current':'Meta+Space','default':'Meta+Space'},
                             {'id':'Amerika: Agent','title':'Amerika Agent','description':'Open Amerika Agent','current':'Meta+A','default':'Meta+A'}]
    notifprefs.known_apps=lambda:['Amerika Agent','Amerika Office','Calendar']
    accessibility.state=lambda:{'text_scale':1.0,'high_contrast':False,'reduce_motion':False,'zoom':False,
                                'sticky_keys':False,'slow_keys':False,'bounce_keys':False,'screen_reader':False,'orca_installed':False}
    datetime_.status=lambda:{'available':True,'clock_24h':True,'ntp':True,'can_ntp':True,'synchronized':True,'timezone':'America/Phoenix'}
    datetime_.timezones=lambda:['America/Phoenix','America/New_York','Europe/London','UTC']
    language.user_settings=lambda:{'lang':'en_US.UTF-8'}
    language.installed=lambda:['en_US.UTF-8','fr_FR.UTF-8']
    defaults.roles=lambda:[{'id':'browser','name':'Web browser','default':'amerika-venture.desktop',
                            'options':[('amerika-venture.desktop','Amerika Venture'),('firefox.desktop','Firefox')]}]
    defaults.autostart_entries=lambda:[{'file':'sample.desktop','name':'Calendar','enabled':True,'comment':'Show upcoming appointments'}]
    accounts.current=lambda:{'username':'eva','real_name':'Eva','admin':True}
    privacy.all_permissions=lambda:[{'table':'devices','resource':'camera','title':'Camera','apps':{'org.example.Meeting':'ask'}}]
    privacy.firewall_enabled=lambda:True
    privacy.firewall_installed=lambda:True
    privacy.recent_enabled=lambda:True
    printers.available=lambda:True
    printers.printers=lambda:[{'name':'Studio','default':True,'state':'idle'}]
    printers.jobs=lambda:[{'queue':'Studio','id':42}]
    storage.volumes=lambda:[{'mount':'/','device':'/dev/nvme0n1p2','size':1000000000000,'used':340000000000,
                            'free':660000000000,'percent':34}]
    storage.home_usage=lambda:[{'name':'Documents','bytes':4200000000},{'name':'Pictures','bytes':12000000000}]
    updates.status=lambda:{'count':2,'security':1,'last_refresh':None,'reboot_required':False,'upgradable':[
        {'name':'amerika-agent','old':'3.0.8','new':'3.1.0~dev'},{'name':'openssl','old':'3.6.0','new':'3.6.1'}]}
