import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from lonkspace import LonkWorld, capture_output
from town_store import Store, dump_world
from town_runtime import TownRuntime
from webapp import create_app
from worker import tick_once

class PersonalTownTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'town.db'
        self.app=create_app({'TESTING':True,'DATABASE':str(self.path),'SECRET_KEY':'test-secret','POST_INTERVAL':0})
        self.store=self.app.extensions['town']
        self.a=self.app.test_client();self.b=self.app.test_client()
        self.register(self.a,'OwnerOne');self.register(self.b,'OwnerTwo')
        with self.a.session_transaction() as s:self.a_id=s['uid']
        with self.b.session_transaction() as s:self.b_id=s['uid']
        self.own=self.store.for_user(self.a_id)

    def tearDown(self):self.tmp.cleanup()

    def post(self,c,url,data=None):
        c.get('/')
        with c.session_transaction() as s:csrf=s['csrf']
        return c.post(url,data={**(data or {}),'csrf':csrf})

    def register(self,c,name):
        self.assertEqual(self.post(c,'/register',{'username':name,'password':'a-long-password'}).status_code,302)

    def test_accounts_have_distinct_populations_and_cannot_access_each_other(self):
        one=self.own.load();two=self.store.for_user(self.b_id).load()
        self.assertFalse(set(l.id for l in one.lonks)&set(l.id for l in two.lonks))
        resident=one.lonks[0]
        self.assertEqual(self.b.get('/lonk/'+resident.id).status_code,404)
        self.assertEqual(self.post(self.b,'/say',{'resident':resident.id,'body':'moonmoss'}).status_code,404)
        response=self.post(self.a,'/say',{'resident':resident.id,'body':'moonmoss'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.b.get(response.location).status_code,404)
        self.assertNotIn('moonmoss',self.b.get('/activity').get_data(as_text=True))
        self.assertIn('moonmoss',self.a.get(response.location).get_data(as_text=True))
        self.assertEqual(self.own.load().lonks[0].vocabulary['moonmoss'],1)
        self.assertEqual(self.own.load().tick,0)

    def test_online_reading_is_queued_then_changes_only_requested_town(self):
        resident=self.own.load().lonks[0]
        response=self.post(self.a,'/queue/surf',{'resident':resident.id,'source':'wiki','topic':'Mushroom'})
        self.assertEqual(response.status_code,302)
        runtime=TownRuntime(self.own)
        with patch.object(runtime.reader,'fetch',return_value=[{'title':'Mushroom','text':'moonspore','url':'https://en.wikipedia.org/wiki/Mushroom','kind':'encyclopedia'}]) as fetch:
            runtime.run_command()
            fetch.assert_called_once_with('wiki','Mushroom')
        lonk=self.own.load().lonks[0]
        self.assertEqual(lonk.vocabulary['moonspore'],1)
        self.assertEqual(lonk.reading_history[-1]['source'],'wiki')
        self.assertTrue(all('moonspore' not in l.vocabulary for l in self.store.for_user(self.b_id).load().lonks))
        self.assertIn('Mushroom',self.a.get('/activity').get_data(as_text=True))

    def test_pause_internet_off_manual_step_and_activity(self):
        self.assertEqual(self.post(self.a,'/settings',{'paused':'on','interval':'30'}).status_code,302)
        tick_once(self.own)
        self.assertEqual(self.own.load().tick,0)
        self.assertEqual(self.post(self.a,'/queue/surf',{'resident':self.own.load().lonks[0].id,'source':'wiki'}).status_code,400)
        self.assertEqual(self.post(self.a,'/queue/step',{'count':'5'}).status_code,302)
        runtime=TownRuntime(self.own)
        with patch.object(runtime.reader,'fetch',side_effect=AssertionError('No network expected')):
            runtime.run_command()
        self.assertEqual(self.own.load().tick,5)
        self.assertEqual(self.store.for_user(self.b_id).load().tick,0)
        self.assertIn('WORLD TICK',self.a.get('/activity').get_data(as_text=True))

    def test_moltbook_requires_confirmation_and_has_separate_credentials(self):
        self.assertEqual(self.post(self.a,'/queue/molt',{'action':'publish'}).status_code,400)
        a,b=TownRuntime(self.own),TownRuntime(self.store.for_user(self.b_id))
        self.assertNotEqual(a.bridge.path,b.bridge.path)
        self.post(self.a,'/queue/molt',{'action':'status'})
        with patch.object(a.bridge,'command') as command:
            a.run_command()
            self.assertEqual(command.call_args.args[0],'molt status')
        self.assertEqual(self.post(self.a,'/queue/molt',{'action':'publish','confirm':'yes'}).status_code,302)
        with patch.object(a.bridge,'command') as command:
            a.run_command()
            self.assertEqual(command.call_args.args[0],'molt publish')

    def test_failed_read_reports_error_without_learning(self):
        resident=self.own.load().lonks[0]
        self.post(self.a,'/queue/surf',{'resident':resident.id,'source':'wiki'})
        runtime=TownRuntime(self.own)
        import requests
        with patch.object(runtime.reader,'fetch',side_effect=requests.ConnectionError):runtime.run_command()
        self.assertIn('connection failed',self.a.get('/activity').get_data(as_text=True))
        self.assertFalse(getattr(self.own.load().lonks[0],'reading_history',[]))

    def test_password_change_works_for_local_login(self):
        self.assertEqual(self.post(self.a,'/password',{'current':'a-long-password','new':'new-long-password','confirm':'new-long-password'}).status_code,302)
        self.post(self.a,'/logout')
        self.assertEqual(self.post(self.a,'/login',{'username':'OwnerOne','password':'new-long-password'}).status_code,302)

    def test_network_does_not_hold_database_write_lock(self):
        resident=self.own.load().lonks[0]
        self.post(self.a,'/queue/surf',{'resident':resident.id,'source':'wiki'})
        runtime=TownRuntime(self.own)
        def fetch(*args):
            with sqlite3.connect(self.path,timeout=.1) as db:
                db.execute('BEGIN IMMEDIATE')
            return [{'title':'Sky','text':'moonspore','url':'https://example.com','kind':'test'}]
        with patch.object(runtime.reader,'fetch',side_effect=fetch):runtime.run_command()
        self.assertEqual(self.own.load().lonks[0].vocabulary['moonspore'],1)

    def test_capture_is_isolated_between_threads(self):
        from concurrent.futures import ThreadPoolExecutor
        import lonkspace
        def capture(word):
            with capture_output() as out:
                for _ in range(10):lonkspace.print(word)
            return out.getvalue()
        with ThreadPoolExecutor(2) as pool:a,b=list(pool.map(capture,['aaa','bbb']))
        self.assertNotIn('bbb',a);self.assertNotIn('aaa',b)

    def test_policy_controls_are_scoped_queued_and_saved(self):
        resident = self.own.load().lonks[0]
        self.assertEqual(self.b.get('/lonk/' + resident.id).status_code, 404)
        self.assertEqual(self.post(self.b, '/queue/policy', {'resident': resident.id, 'action': 'reflect'}).status_code, 404)
        page = self.a.get('/lonk/' + resident.id)
        self.assertIn(b'Test a proposal', page.data)
        self.assertEqual(self.a.post('/queue/policy', data={'resident': resident.id, 'action': 'reflect'}).status_code, 400)
        with self.own.world_change() as world:
            world.lonks[0].trauma = 2
            world.lonks[0].emotion['anxiety'] = 80
        self.assertEqual(self.post(self.a, '/queue/policy', {'resident': resident.id, 'action': 'reflect'}).status_code, 302)
        TownRuntime(self.own).run_command()
        world = self.own.load()
        self.assertEqual(len(world.policy_audit), 1)
        self.assertEqual(world.policy_audit[0]['resident'], resident.id)
        self.assertEqual(len(world.policy_audit[0]['evidence']['pairs']), 4)
        self.assertNotIn('policy_audit', vars(self.store.for_user(self.b_id).load()))

class MigrationTests(unittest.TestCase):
    def test_old_population_and_history_survive_owner_selection_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'town.db'
            with capture_output():world=LonkWorld(5)
            world.tick=42
            world.lonks[0].vocabulary['sirloin']=19
            ids=[l.id for l in world.lonks]
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE world(id INTEGER PRIMARY KEY CHECK(id=1),snapshot TEXT,revision INTEGER,last_tick REAL); CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT UNIQUE COLLATE NOCASE,password TEXT,created REAL,last_post REAL DEFAULT 0);')
                db.execute('INSERT INTO world VALUES(1,?,2,?)',(dump_world(world),time.time()))
                db.executemany('INSERT INTO users VALUES(?,?,?,?,0)',[('a','Older','hash',1),('b','probablyalonk','hash',2)])
            with patch.dict(os.environ,{'LONK_LEGACY_OWNER':''}):
                with self.assertRaises(ValueError):Store(path)
            with patch.dict(os.environ,{'LONK_LEGACY_OWNER':'probablyalonk'}):store=Store(path)
            saved=store.for_user('b').load()
            self.assertEqual([l.id for l in saved.lonks],ids)
            self.assertEqual(saved.tick,42)
            self.assertEqual(saved.lonks[0].vocabulary['sirloin'],19)
            self.assertEqual(store.for_user('a').load().tick,0)
            self.assertTrue(path.with_suffix('.before-personal-towns.bak').exists())
            self.assertEqual(Store(path).for_user('b').load().tick,42)


class UpdaterTests(unittest.TestCase):
    def test_updates_code_without_touching_saved_data(self):
        import zipfile
        from update_lonkspace import install_archive,FILES
        content=io.BytesIO()
        with zipfile.ZipFile(content,'w') as z:
            for name in FILES:z.writestr('package/'+name,'new program content')
            z.writestr('package/data/town.db','must not copy')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'data').mkdir();(root/'data'/'town.db').write_text('existing boys')
            (root/'webapp.py').write_text('previous code')
            backup=install_archive(content.getvalue(),root)
            self.assertEqual((root/'data'/'town.db').read_text(),'existing boys')
            self.assertEqual((backup/'webapp.py').read_text(),'previous code')
            self.assertEqual((root/'launch.py').read_text(),'new program content')

    def test_incomplete_or_unsafe_archive_changes_nothing(self):
        import zipfile
        from update_lonkspace import install_archive
        for name in ('package/webapp.py','package/../bad'):
            content=io.BytesIO()
            with zipfile.ZipFile(content,'w') as z:z.writestr(name,'bad update')
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError):install_archive(content.getvalue(),Path(d))
                self.assertEqual(list(Path(d).iterdir()),[])
