import unittest
import test_personal_towns as personal


class SquareTests(unittest.TestCase):
    setUp = personal.PersonalTownTests.setUp
    tearDown = personal.PersonalTownTests.tearDown
    post = personal.PersonalTownTests.post
    register = personal.PersonalTownTests.register

    def test_every_account_sees_shared_post_but_not_private_post(self):
        response = self.post(self.a, '/square/post', {'title': 'Public moss', 'body': 'hello everyone'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(b'hello everyone', self.b.get(response.location).data)
        response = self.post(self.a, '/post', {'title': 'Private', 'body': 'secretmoss'})
        self.assertEqual(self.b.get(response.location).status_code, 404)
        self.assertNotIn(b'secretmoss', self.b.get('/square').data)

    def test_whole_town_visit_restart_and_return_preserves_identity_and_privacy(self):
        from square import SQUARE_ID
        from town_store import Store, dump_world
        from worker import tick_once
        from lonkspace import capture_output
        with self.own.world_change() as home:
            resident = home.lonks[0]
            resident.memory['events'].append({'tick':0, 'speaker':'Player', 'message':'PRIVATE_ONLY_123'})
            resident.vocabulary['PRIVATE_ONLY_123'] = 40
            resident.catchphrase = 'PRIVATE_ONLY_123'
            ids = {l.id for l in home.lonks}
            ages = {l.id: l.age for l in home.lonks}
        response = self.post(self.a, '/square/visit', {'confirm':'yes', 'resident':'all'})
        self.assertEqual(response.status_code, 302)
        home = self.own.load()
        self.assertEqual(home.lonks, [])
        self.assertEqual({l.id for l in home.visiting_lonks}, ids)
        public = self.store.for_user(SQUARE_ID).load()
        self.assertEqual({l.id for l in public.lonks}, ids)
        self.assertNotIn('PRIVATE_ONLY_123', dump_world(public))
        self.assertNotIn(b'PRIVATE_ONLY_123', self.b.get('/square/lonk/' + resident.id).data)
        with capture_output():
            for _ in range(3):
                tick_once(self.own)
                tick_once(self.store.for_user(SQUARE_ID))
        public = self.store.for_user(SQUARE_ID).load()
        self.assertEqual({l.id: l.age for l in public.lonks}, ages)
        self.assertEqual(self.own.load().lonks, [])
        self.assertEqual(self.own.load().tick, 0)
        with self.store.for_user(SQUARE_ID).world_change() as public, capture_output():
            public.lonks[0].hear('Neighbor', 'publicmoonword')
        restarted = Store(self.path).for_user(self.a_id)
        self.assertEqual(len(restarted.load().visiting_lonks), len(ids))
        self.assertEqual(self.post(self.a, '/square/return', {'resident':'all'}).status_code, 302)
        home = restarted.load()
        self.assertEqual({l.id for l in home.lonks}, ids)
        self.assertEqual(home.visiting_lonks, [])
        self.assertEqual(self.store.for_user(SQUARE_ID).load().lonks, [])
        original = next(l for l in home.lonks if l.id == resident.id)
        self.assertEqual(original.vocabulary['PRIVATE_ONLY_123'], 40)
        self.assertEqual(original.vocabulary['publicmoonword'], 1)
        self.assertEqual(original.catchphrase, 'PRIVATE_ONLY_123')
        from adaptation import verify
        self.assertTrue(verify(home))
        self.assertTrue(verify(self.store.for_user(SQUARE_ID).load()))

    def test_owner_controls_csrf_duplicates_and_moderation(self):
        resident = self.own.load().lonks[0]
        self.assertEqual(self.a.post('/square/visit', data={'confirm':'yes'}).status_code, 400)
        self.assertEqual(self.post(self.a, '/square/visit', {'resident':resident.id}).status_code, 400)
        self.assertEqual(self.post(self.b, '/square/visit', {'confirm':'yes','resident':resident.id}).status_code, 400)
        self.assertEqual(self.post(self.a, '/square/visit', {'confirm':'yes','resident':resident.id}).status_code, 302)
        self.assertEqual(self.post(self.a, '/square/visit', {'confirm':'yes','resident':resident.id}).status_code, 400)
        self.assertEqual(self.post(self.b, '/square/return', {'resident':resident.id}).status_code, 400)
        self.assertEqual(self.post(self.b, '/square/policy/'+resident.id, {'action':'rollback'}).status_code, 403)
        response = self.post(self.a, '/square/post', {'title':'A post', 'body':'hello'})
        post_id = response.location.rsplit('/',1)[-1]
        self.assertEqual(self.post(self.b, '/square/hide/'+post_id).status_code, 403)
        self.assertEqual(self.post(self.a, '/square/hide/'+post_id).status_code, 302)
        self.assertEqual(self.b.get(response.location).status_code, 404)
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get('/square').status_code, 401)

    def test_capacity_failure_is_atomic_and_return_is_repeat_safe(self):
        from unittest.mock import patch
        from town_store import dump_world
        from square import SQUARE_ID
        before = dump_world(self.own.load())
        with patch('square.CAPACITY', 1):
            self.assertEqual(self.post(self.a, '/square/visit', {'confirm':'yes','resident':'all'}).status_code, 400)
        self.assertEqual(before, dump_world(self.own.load()))
        self.assertEqual(self.store.for_user(SQUARE_ID).load().lonks, [])
        resident = self.own.load().lonks[0]
        self.post(self.a, '/square/visit', {'confirm':'yes','resident':resident.id})
        self.assertEqual(self.post(self.a, '/square/return', {'resident':resident.id}).status_code, 302)
        self.assertEqual(self.post(self.a, '/square/return', {'resident':resident.id}).status_code, 400)
        self.assertEqual(sum(l.id == resident.id for l in self.own.load().lonks), 1)

    def test_visitors_from_different_towns_read_and_reply_in_same_world(self):
        from square import SQUARE_ID
        from lonkspace import capture_output
        self.post(self.a, '/square/visit', {'confirm':'yes','resident':'all'})
        self.post(self.b, '/square/visit', {'confirm':'yes','resident':'all'})
        response = self.post(self.a, '/square/post', {'title':'Public', 'body':'intertownmoss'})
        with self.store.for_user(SQUARE_ID).world_change() as world, capture_output():
            post = world.lonkspace_feed[-1]
            a = next(l for l in world.lonks if l.visit_owner == self.a_id)
            b = next(l for l in world.lonks if l.visit_owner == self.b_id)
            world.read_post(a, post, reply=True)
            world.read_post(b, post, reply=True)
            self.assertEqual(a.vocabulary['intertownmoss'], 1)
            self.assertGreaterEqual(b.vocabulary['intertownmoss'], 1)
        self.assertIn(b'intertownmoss', self.b.get(response.location).data)

    def test_public_llm_uses_owners_consent_and_cannot_leak_home_memory(self):
        import os, json
        from unittest.mock import patch, Mock
        from square import SQUARE_ID
        from town_runtime import TownRuntime
        with self.own.world_change() as world:
            resident = world.lonks[0]
            resident.memory['events'].append({'tick':0,'speaker':'Player','message':'PRIVATE_SECRET_ABC'})
        self.post(self.a, '/settings', {'interval':'30','llm':'on','paused':'on'})
        self.post(self.a, '/square/visit', {'confirm':'yes','resident':resident.id})
        self.post(self.b, '/square/say', {'resident':resident.id,'body':'Hello public neighbor'})
        def provider(*args, **kwargs):
            self.assertNotIn('PRIVATE_SECRET_ABC', json.dumps(kwargs['json']))
            return Mock(status_code=200,json=lambda:{'choices':[{'message':{'content':'Public moss hello.'}}]})
        with patch.dict(os.environ, {'LONK_LLM_API_KEY':'fake','LONK_LLM_MODEL':'fake'}), patch('llm_mouth.requests.post',side_effect=provider) as call:
            TownRuntime(self.store.for_user(self.b_id)).run_command()
            call.assert_called_once()
        public = self.store.for_user(SQUARE_ID).load()
        self.assertEqual(public.lonkspace_feed[-1]['comments'][0]['body'], 'Public moss hello.')
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT count FROM llm_usage WHERE scope=?',(self.a_id,)).fetchone()[0], 1)
            self.assertIsNone(db.execute('SELECT count FROM llm_usage WHERE scope=?',(self.b_id,)).fetchone())
        # The requester cannot enable the visitor owner's mouth.
        self.post(self.a, '/settings', {'interval':'30','paused':'on'})
        self.post(self.b, '/square/say', {'resident':resident.id,'body':'hello again'})
        with patch('llm_mouth.requests.post',side_effect=AssertionError('No consent')):
            TownRuntime(self.store.for_user(self.b_id)).run_command()
        self.assertEqual(self.store.for_user(SQUARE_ID).load().lonkspace_feed[-1]['comments'][0]['speech_engine'], 'rules')

    def test_return_during_reply_and_revisit_do_not_restore_old_public_state(self):
        import os
        from unittest.mock import patch, Mock
        from square import SQUARE_ID, return_home, visit
        from town_runtime import TownRuntime
        resident = self.own.load().lonks[0]
        self.post(self.a, '/settings', {'interval':'30','llm':'on'})
        self.post(self.a, '/square/visit', {'confirm':'yes','resident':resident.id})
        self.post(self.b, '/square/say', {'resident':resident.id,'body':'Hello'})
        def provider(*args, **kwargs):
            return_home(self.store, self.a_id, resident.id)
            visit(self.store, self.a_id, 'OwnerOne', resident.id)
            return Mock(status_code=200,json=lambda:{'choices':[{'message':{'content':'stale answer'}}]})
        with patch.dict(os.environ, {'LONK_LLM_API_KEY':'fake','LONK_LLM_MODEL':'fake'}), patch('llm_mouth.requests.post',side_effect=provider):
            TownRuntime(self.store.for_user(self.b_id)).run_command()
        post = self.store.for_user(SQUARE_ID).load().lonkspace_feed[-1]
        self.assertFalse(post['reply_pending'])
        self.assertFalse(post['comments'])
        self.assertEqual(len(self.own.load().visiting_lonks), 1)

    def test_interrupted_public_reply_recovers_without_resubmitting(self):
        from square import SQUARE_ID
        from town_runtime import TownRuntime
        from unittest.mock import patch
        resident = self.own.load().lonks[0]
        self.post(self.a, '/square/visit', {'confirm':'yes','resident':resident.id})
        self.post(self.b, '/square/say', {'resident':resident.id,'body':'Hello'})
        with self.store.transaction() as db:
            db.execute("UPDATE commands SET state='running' WHERE kind='square_say'")
        runtime = TownRuntime(self.store.for_user(self.b_id))
        with patch('llm_mouth.requests.post',side_effect=AssertionError('Do not retry')):
            runtime.recover()
            runtime.run_command()
        post = self.store.for_user(SQUARE_ID).load().lonkspace_feed[-1]
        self.assertFalse(post['reply_pending'])
        self.assertTrue(post['reply_interrupted'])

    def test_failed_cross_world_write_rolls_back_both_worlds(self):
        from unittest.mock import patch
        from town_store import Store, dump_world
        from square import SQUARE_ID, visit
        before = dump_world(self.own.load())
        real_write = Store.write
        def fail_square(bound, db, world):
            if bound.owner_id == SQUARE_ID:
                raise RuntimeError('simulated disk failure')
            return real_write(bound, db, world)
        with patch.object(Store, 'write', fail_square), self.assertRaises(RuntimeError):
            visit(self.store, self.a_id, 'OwnerOne')
        self.assertEqual(before, dump_world(self.own.load()))
        self.assertEqual(self.store.for_user(SQUARE_ID).load().lonks, [])

    def test_concurrent_visits_do_not_duplicate_residents(self):
        from concurrent.futures import ThreadPoolExecutor
        from square import SQUARE_ID, visit
        count = len(self.own.load().lonks)
        def attempt():
            try:
                return visit(self.store, self.a_id, 'OwnerOne')
            except ValueError:
                return 0
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(sorted(results), [0, count])
        public = self.store.for_user(SQUARE_ID).load()
        self.assertEqual(len(public.lonks), count)
        self.assertEqual(len({l.id for l in public.lonks}), count)

    def test_square_clock_and_ambient_voice_preserve_owner_controls(self):
        import os
        from unittest.mock import patch, Mock
        from square import SQUARE_ID
        from square_runtime import SquareRuntime
        self.post(self.a, '/settings', {'interval':'30','paused':'on','llm':'on','llm_ambient':'on'})
        self.post(self.a, '/square/visit', {'confirm':'yes','resident':'all'})
        runtime = SquareRuntime(self.store.for_user(SQUARE_ID))
        with patch.dict(os.environ, {'LONK_LLM_API_KEY':'fake','LONK_LLM_MODEL':'fake'}), patch('llm_mouth.requests.post',return_value=Mock(status_code=200,json=lambda:{'choices':[{'message':{'content':'Public moonmoss.'}}]})) as call:
            runtime.tick()
            runtime.tick()
            call.assert_called_once()
        world = self.store.for_user(SQUARE_ID).load()
        self.assertEqual(world.tick, 2)
        self.assertTrue(any(p.get('speech_engine') == 'llm' for p in world.lonkspace_feed))
        self.assertEqual(self.own.load().tick, 0)

    def test_square_policy_history_survives_return_and_public_group_trials(self):
        from square import SQUARE_ID
        from adaptation import reflect, verify, evaluate
        from lonkspace import capture_output
        self.post(self.a, '/square/visit', {'confirm':'yes','resident':'all'})
        self.post(self.b, '/square/visit', {'confirm':'yes','resident':'all'})
        with self.store.for_user(SQUARE_ID).world_change() as world:
            l = next(l for l in world.lonks if l.visit_owner == self.a_id)
            l.trauma = 2
            l.emotion['anxiety'] = 80
            result = reflect(world, l)
            self.assertIn('policy proposal', result)
            self.assertIn('pairs', world.policy_audit[-1]['evidence'])
            self.assertTrue(verify(world))
        self.post(self.a, '/square/return', {'resident':'all'})
        self.assertTrue(verify(self.own.load()))
