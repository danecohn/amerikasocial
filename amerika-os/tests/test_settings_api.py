"""Settings API boundaries and notification schedule policy; no system changes."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/os'))
from amerika import common,notifprefs
from amerika.settings import api,pageindex,search
from amerika.shell.clipboard import History
from amerika.shell.switcher import candidates


class Settings(unittest.TestCase):
    def test_strict_write_allowlist(self):
        for key,value in [('ai',{}),('ai.mode','trusted'),('dock_size',True),('dock_size',100),('clock_24h','yes'),
                          ('copilot_app','evil'),('wallpaper','../../bad'),('accent','#fff')]:
            with self.subTest(key=key),self.assertRaises(ValueError):api.validate(key,value)
        for key,value in [('dock_size',56),('clock_24h',False),('copilot_app','agent'),('accent','#abcdef')]:
            self.assertEqual(api.validate(key,value),value)

    def test_settings_are_private_and_other_fields_survive(self):
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(common,'CONFIG',Path(tmp)):
            common.save_settings(dict(common.DEFAULTS,extra='preserve me'))
            api.set('clock_24h',True)
            self.assertEqual(common.load_settings()['extra'],'preserve me')
            self.assertEqual((Path(tmp)/'settings.json').stat().st_mode&0o777,0o600)
            self.assertNotIn('ai',api.get())

    def test_search_deep_links_are_indexed(self):
        self.assertEqual(len(pageindex.page_ids()),24)   # studio-core added Amerika Studio
        for query,page in [('microphone','sound'),('compose','input'),('gateway','agent')]:
            self.assertIn(page,{r['page'] for r in search.search(query)})

    def test_notification_schedule_crosses_midnight(self):
        cfg=copy.deepcopy(notifprefs.DEFAULT);cfg['schedule']={'enabled':True,'from':'22:00','to':'07:00'}
        from datetime import datetime
        import time
        night=time.localtime(datetime(2026,10,21,23,0).timestamp())
        day=time.localtime(datetime(2026,10,21,12,0).timestamp())
        self.assertTrue(notifprefs.schedule_active(cfg,night));self.assertFalse(notifprefs.schedule_active(cfg,day))
        self.assertFalse(notifprefs.allows('Mail',now=night,cfg=cfg));self.assertTrue(notifprefs.allows('Mail',urgency=2,now=night,cfg=cfg))
        cfg['apps']['Mail']={'enabled':False}
        self.assertFalse(notifprefs.allows('Mail',urgency=2,now=day,cfg=cfg))


class DesktopModels(unittest.TestCase):
    def test_clipboard_deduplicates_bounds_and_ignores_sensitive(self):
        history=History(limit=2,max_bytes=10)
        self.assertFalse(history.add('password',sensitive=True));self.assertFalse(history.add('x'*11))
        history.add('one');history.add('two');history.add('one');history.add('three')
        self.assertEqual(history.items,['three','one']);history.clear();self.assertEqual(history.items,[])

    def test_switcher_filters_and_orders_windows(self):
        state={'current':1,'mru':['b','a','c'],'windows':[
            {'id':'a','normal':True,'desktops':[1],'cls':'editor','active':True},
            {'id':'b','normal':True,'desktops':[2],'cls':'editor'},
            {'id':'c','normal':True,'desktops':[1],'cls':'browser','minimized':True}]}
        self.assertEqual([w['id'] for w in candidates(state)],['b','a','c'])
        self.assertEqual([w['id'] for w in candidates(state,{'all_desktops':False,'include_minimized':False})],['a'])
        self.assertEqual([w['id'] for w in candidates(state,app_only=True)],['b','a'])


class DisplayRollback(unittest.TestCase):
    def test_rejection_timeout_and_owner_exit_restore_original_mode(self):
        import io
        from amerika import displays
        original={'name':'eDP-1','mode':{'id':'1'},'scale':1.0,'x':0,'y':0,'rotation':'normal'}
        for response,ready in [('revert\n',True),('',True),('',False)]:
            with mock.patch.object(displays,'outputs',return_value=[original]), mock.patch.object(displays,'apply') as apply, \
                 mock.patch('select.select',return_value=([1],[],[]) if ready else ([],[],[])):
                self.assertFalse(displays.preview([('eDP-1','scale',1.5)],io.StringIO(response),io.StringIO(),timeout=1))
                self.assertEqual(apply.call_args.args[0],[('eDP-1','scale',1.0)])

    def test_keep_and_apply_failure(self):
        import io
        from amerika import displays
        original={'name':'eDP-1','mode':{'id':'1'},'scale':1.0,'x':0,'y':0,'rotation':'normal'}
        with mock.patch.object(displays,'outputs',return_value=[original]), mock.patch.object(displays,'apply') as apply, \
             mock.patch('select.select',return_value=([1],[],[])):
            self.assertTrue(displays.preview([('eDP-1','scale',1.5)],io.StringIO('keep\n'),io.StringIO()))
            self.assertEqual(apply.call_count,1)
        with mock.patch.object(displays,'outputs',return_value=[original]), mock.patch.object(displays,'apply',side_effect=[RuntimeError('failed'),[]]) as apply:
            with self.assertRaises(RuntimeError):displays.preview([('eDP-1','scale',1.5)],io.StringIO(''),io.StringIO())
            self.assertEqual(apply.call_count,2)
