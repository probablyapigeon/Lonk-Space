import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from town_store import Store

class TownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'town.db')

    def tearDown(self):
        self.tmp.cleanup()

    def test_post_hearing_reply_and_restart(self):
        with self.store.world_change() as world:
            lonk = world.lonks[0]
            lonk_id = lonk.id
            post = world.add_post('Visitor', 'Human hello', 'mossfriend', 'human', 'human-1')
            world.add_comment(post['id'], 'Visitor', 'sporefriend', 'human', 'human-1')
            with contextlib.redirect_stdout(io.StringIO()):
                world.read_post(lonk, post, reply=True)
            self.assertEqual(lonk.vocabulary['mossfriend'], 1)
            self.assertEqual(lonk.vocabulary['sporefriend'], 1)
            self.assertEqual(post['comments'][-1]['author_id'], lonk_id)
            self.assertEqual(post['readers'][0]['lonk_id'], lonk_id)
            self.assertEqual(lonk.memory['events'][-1]['source_post_id'], post['id'])
        restored = Store(self.store.path).load()
        lonk = next(l for l in restored.lonks if l.id == lonk_id)
        self.assertEqual(lonk.vocabulary['mossfriend'], 1)
        self.assertIs(lonk.world, restored)
        self.assertEqual(restored.lonkspace_feed[-1]['comments'][-1]['author_id'], lonk_id)


class WebTests(unittest.TestCase):
    def setUp(self):
        from webapp import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.config = {'TESTING': True, 'DATABASE': str(Path(self.tmp.name)/'town.db'),
                       'SECRET_KEY': 'test-only-secret-key', 'POST_INTERVAL': 0}
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.store = self.app.extensions['town']

    def tearDown(self):
        self.tmp.cleanup()

    def submit(self, path, data=None, client=None):
        client = client or self.client
        client.get('/')
        with client.session_transaction() as sess:
            csrf = sess['csrf']
        return client.post(path, data={**(data or {}), 'csrf': csrf})

    def register(self, name='HumanOne', client=None):
        return self.submit('/register', {'username': name, 'password': 'a-long-test-password'}, client)

    def test_browser_post_to_lonk_to_reply_survives_restart(self):
        from webapp import create_app
        self.assertEqual(self.register().status_code, 302)
        response = self.submit('/post', {'title': 'Hello neighbors', 'body': 'mossfriend'})
        self.assertEqual(response.status_code, 302)
        thread_url = response.location
        self.assertEqual(self.client.get(thread_url).status_code, 200)
        post_id = thread_url.rsplit('/',1)[-1]
        self.assertEqual(self.submit('/post', {'parent': post_id, 'body': 'sporefriend'}).status_code, 302)
        with self.store.world_change() as world:
            lonk = world.lonks[0]
            lonk_id = lonk.id
            lonk.vocabulary.clear()
            with contextlib.redirect_stdout(io.StringIO()):
                world.read_post(lonk, world.lonkspace_feed[-1], reply=True)
        app2 = create_app(self.config)
        restored = app2.extensions['town'].load()
        self.assertEqual(restored.lonks[0].vocabulary['mossfriend'], 1)
        self.assertEqual(restored.lonks[0].vocabulary['sporefriend'], 1)
        page = self.client.get('/lonk/' + lonk_id).get_data(as_text=True)
        self.assertIn('mossfriend', page)
        self.assertIn(thread_url, page)
        self.assertIn(lonk_id, self.client.get(thread_url).get_data(as_text=True))
        self.submit('/logout')
        self.assertEqual(self.submit('/login', {'username': 'HumanOne', 'password': 'a-long-test-password'}).status_code, 302)

    def test_csrf_auth_xss_and_permissions(self):
        self.assertEqual(self.client.post('/post', data={'body': 'hi'}).status_code, 400)
        self.assertEqual(self.submit('/post', {'title': 'hi','body':'hello'}).status_code, 401)
        self.register()
        response = self.submit('/post', {'title': '<script>alert(1)</script>', 'body': '<img src=x onerror=alert(1)>'})
        page = self.client.get(response.location).get_data(as_text=True)
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<img src=x', page)
        other = self.app.test_client()
        self.register('HumanTwo', other)
        post_id = response.location.rsplit('/',1)[-1]
        self.assertEqual(self.submit('/hide/'+post_id, client=other).status_code, 404)
        self.assertEqual(self.submit('/hide/'+post_id).status_code, 302)
        self.assertEqual(self.client.get(response.location).status_code, 404)

    def test_duplicate_account_limits_and_invalid_thread(self):
        self.register()
        self.submit('/logout')
        self.assertEqual(self.register('humanone').status_code, 400)
        self.assertEqual(self.submit('/login', {'username':'HumanOne', 'password':'not-the-right-password'}).status_code, 401)
        self.submit('/login', {'username':'HumanOne', 'password':'a-long-test-password'})
        self.assertEqual(self.submit('/post', {'parent':'missing', 'body':'hello'}).status_code, 404)
        self.app.config['POST_INTERVAL'] = 10
        self.assertEqual(self.submit('/post', {'title':'One', 'body':'hello'}).status_code, 302)
        self.assertEqual(self.submit('/post', {'title':'Two', 'body':'hello'}).status_code, 429)
        self.assertEqual(self.submit('/post', {'title':'Long', 'body':'x'*2001}).status_code, 400)

    def test_multiple_visitors_do_not_tick_or_create_world(self):
        before = self.store.load()
        for _ in range(5):
            self.assertEqual(self.app.test_client().get('/').status_code, 200)
        after = self.store.load()
        self.assertEqual(after.tick, before.tick)
        self.assertEqual([l.id for l in after.lonks], [l.id for l in before.lonks])

    def test_worker_and_concurrent_human_writes(self):
        from concurrent.futures import ThreadPoolExecutor
        from worker import tick_once
        def write(i):
            with self.store.world_change() as world:
                world.add_post('Visitor', f'Concurrent {i}', 'hello', 'human', str(i))
        with contextlib.redirect_stdout(io.StringIO()):
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(write, range(8)))
            tick_once(self.store)
        world = self.store.load()
        self.assertEqual(world.tick, 1)
        self.assertEqual(len([p for p in world.lonkspace_feed if p['title'].startswith('Concurrent')]), 8)

    def test_snapshot_graph_and_transaction_rollback(self):
        with self.store.world_change() as world:
            a,b = world.lonks[:2]
            a.rival = b
            a.memory['player_words'].add('moss')
        world = self.store.load()
        self.assertIs(world.lonks[0].rival, world.lonks[1])
        self.assertEqual(world.lonks[0].memory['player_words'], {'moss'})
        tick = world.tick
        with self.assertRaises(RuntimeError):
            with self.store.world_change() as world:
                world.tick += 10
                raise RuntimeError('interrupted tick')
        self.assertEqual(self.store.load().tick, tick)

    def test_second_worker_rejected(self):
        from worker import worker_lock
        with worker_lock(str(self.store.path)+'.lock'):
            with self.assertRaises(RuntimeError):
                with worker_lock(str(self.store.path)+'.lock'):
                    pass

    def test_worker_encounters_human_post_through_normal_tick(self):
        from unittest.mock import patch
        from worker import tick_once
        with self.store.world_change() as world:
            post = world.add_post('HumanOne', 'Hello', 'moonmoss', 'human', 'human-1')
            world.lonkspace_feed = [post]
            original_id = world.lonks[0].id
            for lonk in world.lonks:
                lonk.job = 'Gatherer'
        with contextlib.redirect_stdout(io.StringIO()), patch('lonkspace.random.random', return_value=0.1):
            tick_once(self.store)
        world = self.store.load()
        resident = next(l for l in world.lonks if l.id == original_id)
        self.assertGreater(resident.vocabulary['moonmoss'], 0)
        self.assertTrue(world.lonkspace_feed[0]['readers'])
        self.assertTrue(any(c['author_type'] == 'lonk' for c in world.lonkspace_feed[0]['comments']))

    def test_hosted_population_stays_bounded(self):
        import random
        from worker import tick_once
        random.seed(42)
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(100):
                tick_once(self.store)
                self.assertLessEqual(len(self.store.load().lonks), 20)
        self.assertEqual(self.store.load().tick, 100)

if __name__ == '__main__':
    unittest.main()
