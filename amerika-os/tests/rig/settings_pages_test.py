"""Build every registered page in a private session; no system mutations."""
import os
from pathlib import Path
from agent_rig import spin,shot,settle,widget_texts
os.environ['AMERIKA_SETTINGS_FAKE']='1'
from amerika.settings.app import SettingsApp,PAGES
from amerika.settings import pageindex
app=SettingsApp();assert app.register(None);app.activate()
assert {p[0] for p in PAGES}==set(pageindex.page_ids())
for key,*_ in PAGES:
    app.show_page(key)
    container=app._built[key].get_child()
    controller=getattr(container,'controller',None)
    if controller:
        spin(lambda:controller.loaded and not controller.busy,timeout=12,what=key)
        assert not controller.message.get_text(),(key,controller.message.get_text())
    settle(.15)
    assert 'This page could not be loaded.' not in widget_texts(container),key
    shot(app.win,'settings-'+key+'.png')
print('SETTINGS ALL PAGES OK: '+str(len(PAGES)),flush=True)
