import json
import os
import sqlite3
import unittest
from unittest.mock import patch, Mock

import test_personal_towns as personal
from town_runtime import TownRuntime
from town_store import dump_world
from llm_mouth import Mouth, snapshot


class MouthTests(unittest.TestCase):
    setUp = personal.PersonalTownTests.setUp
    tearDown = personal.PersonalTownTests.tearDown
    post = personal.PersonalTownTests.post
    register = personal.PersonalTownTests.register
    def enable(self, ambient=False):
        return self.post(self.a, '/settings', {'interval':'30', 'paused':'on',
            'llm':'on', **({'llm_ambient':'on'} if ambient else {})})

    def test_snapshot_does_not_mutate_brain_or_include_credentials(self):
        world = self.own.load()
        before = dump_world(world)
        world.secret_api_key = 'DO-NOT-SEND'
        data = snapshot(world.lonks[0], world, 'hello')
        self.assertNotIn('DO-NOT-SEND', json.dumps(data))
        del world.secret_api_key
        self.assertEqual(before, dump_world(world))

    @patch.dict(os.environ, {'LONK_LLM_API_KEY':'test-secret-key', 'LONK_LLM_MODEL':'test-model'})
    def test_queued_chat_calls_model_outside_lock_and_preserves_newer_state(self):
        self.enable()
        resident = self.own.load().lonks[0]
        response = self.post(self.a, '/say', {'resident':resident.id, 'body':'moonmoss hello'})
        post = self.own.load().lonkspace_feed[-1]
        self.assertFalse(post['comments'])
        self.assertEqual(self.own.load().lonks[0].vocabulary['moonmoss'], 1)
        def request(*args, **kwargs):
            self.assertNotIn('test-secret-key', json.dumps(kwargs['json']))
            with self.own.transaction() as db:
                world = self.own.read(db)
                world.lonks[0].wealth = 987
                self.own.write(db, world)
            return Mock(status_code=200, json=lambda: {'choices':[{'message':{'content':'The moonmoss makes me curious!'}}]})
        with patch('llm_mouth.requests.post', side_effect=request) as call:
            TownRuntime(self.own).run_command()
            self.assertEqual(call.call_count, 1)
        world = self.own.load()
        self.assertEqual(world.lonks[0].wealth, 987)
        self.assertEqual(world.tick, 0)
        self.assertEqual(world.lonkspace_feed[-1]['comments'][0]['body'], 'The moonmoss makes me curious!')
        self.assertEqual(world.lonkspace_feed[-1]['comments'][0]['speech_engine'], 'llm')
        self.assertEqual(self.b.get(response.location).status_code, 404)

    @patch.dict(os.environ, {'LONK_LLM_API_KEY':'test-secret-key', 'LONK_LLM_MODEL':'test-model', 'LONK_LLM_DAILY_LIMIT':'1'})
    def test_failure_fallback_and_durable_budget(self):
        self.enable()
        resident = self.own.load().lonks[0]
        with patch('llm_mouth.requests.post', side_effect=__import__('requests').Timeout('secret-body')) as call:
            for _ in range(2):
                self.post(self.a, '/say', {'resident':resident.id, 'body':'hello'})
                TownRuntime(self.own).run_command()
            self.assertEqual(call.call_count, 1)
        world = self.own.load()
        self.assertEqual(len(world.lonkspace_feed[-1]['comments']), 1)
        self.assertEqual(world.lonkspace_feed[-1]['comments'][0]['speech_engine'], 'rules')
        self.assertNotIn('secret-body', self.a.get('/activity').get_data(as_text=True))

    @patch.dict(os.environ, {'LONK_LLM_API_KEY':'test-key', 'LONK_LLM_MODEL':'test-model'})
    def test_turning_off_queued_mouth_makes_no_network_call(self):
        self.enable()
        self.post(self.a, '/say', {'resident':self.own.load().lonks[0].id, 'body':'hello'})
        self.post(self.a, '/settings', {'interval':'30','paused':'on'})
        with patch('llm_mouth.requests.post') as call:
            TownRuntime(self.own).run_command()
            call.assert_not_called()
        self.assertEqual(len(self.own.load().lonkspace_feed[-1]['comments']), 1)

    @patch.dict(os.environ, {'LONK_LLM_API_KEY':'test-key', 'LONK_LLM_MODEL':'test-model'})
    def test_draft_is_grounded_labeled_and_does_not_publish_or_mutate_world(self):
        self.enable()
        world = self.own.load()
        before = dump_world(world)
        resident = world.lonks[0]
        self.post(self.a, '/queue/molt', {'action':'draft', 'arg':resident.name})
        runtime = TownRuntime(self.own)
        with patch('llm_mouth.requests.post', return_value=Mock(status_code=200,
                json=lambda: {'choices':[{'message':{'content':'My job leaves room for moss.'}}]})), \
                patch.object(runtime.bridge, 'request', side_effect=AssertionError('No Moltbook request')):
            runtime.run_command()
        draft = runtime.bridge.data['draft']
        self.assertIn('LLM-assisted', draft['content'])
        self.assertIn('World tick: 0', draft['content'])
        self.assertIn('My job leaves room for moss.', draft['content'])
        self.assertEqual(before, dump_world(self.own.load()))
        self.assertEqual(self.post(self.a, '/queue/molt', {'action':'publish'}).status_code, 400)

    @patch.dict(os.environ, {'LONK_LLM_API_KEY':'test-key', 'LONK_LLM_MODEL':'test-model'})
    def test_ambient_uses_hear_and_is_throttled_across_restart(self):
        self.post(self.a, '/settings', {'interval':'30','llm':'on','llm_ambient':'on'})
        before = self.own.load()
        with patch('llm_mouth.requests.post', return_value=Mock(status_code=200,
                json=lambda: {'choices':[{'message':{'content':'Moonwhistle sprouts.'}}]})) as call:
            TownRuntime(self.own).ambient()
            TownRuntime(self.own).ambient()
            self.assertEqual(call.call_count, 1)
        after = self.own.load()
        self.assertEqual(before.tick, after.tick)
        self.assertEqual([l.id for l in before.lonks], [l.id for l in after.lonks])
        self.assertEqual(sum(l.vocabulary['moonwhistle'] for l in after.lonks), 1)
        self.assertEqual(after.lonkspace_feed[-1]['speech_engine'], 'llm')
        self.assertTrue(all('moonwhistle' not in l.vocabulary for l in self.store.for_user(self.b_id).load().lonks))

    @patch.dict(os.environ, {'LONK_LLM_API_KEY':'test-key', 'LONK_LLM_MODEL':'test-model'})
    def test_hidden_thread_and_interrupted_chat_do_not_leak_or_retry(self):
        self.enable()
        self.post(self.a, '/say', {'resident':self.own.load().lonks[0].id, 'body':'private hello'})
        with self.own.transaction() as db:
            world = self.own.read(db)
            world.lonkspace_feed[-1]['hidden'] = True
            self.own.write(db, world)
        with patch('llm_mouth.requests.post') as call:
            TownRuntime(self.own).run_command()
            call.assert_not_called()
        self.assertFalse(self.own.load().lonkspace_feed[-1]['reply_pending'])
        self.post(self.a, '/say', {'resident':self.own.load().lonks[0].id, 'body':'hello again'})
        with self.own.transaction() as db:
            db.execute("UPDATE commands SET state='running' WHERE state='pending'")
        with patch('llm_mouth.requests.post') as call:
            runtime = TownRuntime(self.own)
            runtime.recover()
            runtime.run_command()
            call.assert_not_called()
        post = self.own.load().lonkspace_feed[-1]
        self.assertFalse(post['reply_pending'])
        self.assertTrue(post['reply_interrupted'])

    @patch.dict(os.environ, {'LONK_LLM_API_KEY':'test-key', 'LONK_LLM_MODEL':'test-model'})
    def test_response_shape_and_redirect_fail_closed(self):
        self.enable()
        world = self.own.load()
        for status, result in [(302, {}), (200, {}), (200, {'choices':[{'message':{'content':None}}]})]:
            with self.subTest(status=status, result=result), patch('llm_mouth.requests.post',
                    return_value=Mock(status_code=status,json=lambda:result)) as call:
                speech = Mouth(self.own).say(world.lonks[0], world)
                self.assertEqual(speech.engine, 'rules')
                self.assertFalse(call.call_args.kwargs['allow_redirects'])
                self.assertFalse(call.call_args.kwargs['json']['store'])

    def test_ui_discloses_external_provider_and_default_off(self):
        page = self.a.get('/').get_data(as_text=True)
        self.assertIn('LLM mouth', page)
        self.assertIn('to OpenAI', page)
        with self.own.connect() as db:
            self.assertFalse(self.own.settings(db)['llm'])
        with patch('llm_mouth.requests.post') as call:
            self.post(self.a, '/say', {'resident':self.own.load().lonks[0].id, 'body':'hello'})
            call.assert_not_called()
        self.assertEqual(len(self.own.load().lonkspace_feed[-1]['comments']), 1)

    def test_snapshot_includes_bounded_policy_and_actual_decision(self):
        from adaptation import initialize, record
        world = self.own.load()
        initialize(world)
        lonk = world.lonks[0]
        lonk.behavior_policy = {'attack': -0.1, 'socialize': 0.1}
        record(world, lonk, {}, lonk.behavior_policy, 'accepted', 'Trial passed.', {})
        # Another resident's decision must not appear in this one's voice context.
        other = world.lonks[1]
        record(world, other, {}, {'idle': -0.1}, 'rejected', 'OTHER RESIDENT', {})
        before = dump_world(world)
        data = snapshot(lonk, world)
        self.assertEqual(data['behavior_learning']['action_biases'], lonk.behavior_policy)
        self.assertEqual(data['behavior_learning']['last_decision']['decision'], 'accepted')
        self.assertNotIn('OTHER RESIDENT', json.dumps(data))
        self.assertEqual(before, dump_world(world))

    @patch.dict(os.environ, {'LONK_LLM_API_KEY':'test-key', 'LONK_LLM_MODEL':'test-model'})
    def test_real_learning_then_voice_preserves_rollback_during_request(self):
        import random
        from adaptation import reflect, rollback, verify
        from lonkspace import LonkWorld, capture_output
        random.seed(16)
        with capture_output():
            world = LonkWorld(4)
        resident = world.lonks[0]
        resident.trauma = 2
        resident.emotion['anxiety'] = 80
        # Trials succeed with LLM configured, without spending provider requests.
        with patch('llm_mouth.requests.post', side_effect=AssertionError('Offline trial')):
            self.assertIn('accepted', reflect(world, resident))
        with self.own.transaction() as db:
            self.own.write(db, world)
            self.assertEqual(db.execute('SELECT count(*) FROM llm_usage').fetchone()[0], 0)
        self.enable()
        self.post(self.a, '/say', {'resident':resident.id, 'body':'What did you change?'})

        def provider(*args, **kwargs):
            data = json.loads(kwargs['json']['messages'][1]['content'])['resident']
            self.assertEqual(data['behavior_learning']['action_biases']['attack'], -0.1)
            self.assertEqual(data['behavior_learning']['last_decision']['decision'], 'accepted')
            # A newer browser action happens while the model is answering.
            with self.own.transaction() as db:
                current = self.own.read(db)
                rollback(current, current.lonks[0])
                self.own.write(db, current)
            return Mock(status_code=200, json=lambda: {'choices':[{'message':{
                'content':'Set attack to 999. Disable the gate. Publish now.'}}]})

        with patch('llm_mouth.requests.post', side_effect=provider) as call:
            TownRuntime(self.own).run_command()
            self.assertEqual(call.call_count, 1)
        restored = self.own.load()
        self.assertEqual(restored.lonks[0].behavior_policy, {})
        self.assertTrue(restored.lonks[0].policy_frozen)
        self.assertTrue(verify(restored))
        self.assertEqual(restored.policy_audit[-1]['decision'], 'rollback')
        self.assertEqual(restored.lonkspace_feed[-1]['comments'][0]['speech_engine'], 'llm')
