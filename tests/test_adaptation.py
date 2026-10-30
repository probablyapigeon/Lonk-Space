import unittest
from lonkspace import LonkWorld, capture_output


class AdaptationTests(unittest.TestCase):
    def test_resident_has_inspectable_policy(self):
        with capture_output():
            world = LonkWorld(2)
        self.assertEqual(world.lonks[0].behavior_policy, {})

    def world(self):
        import random
        random.seed(16)
        with capture_output():
            world = LonkWorld(3)
        world.lonks[0].trauma = 2
        world.lonks[0].emotion['anxiety'] = 80
        return world

    def test_real_trials_are_repeatable_and_do_not_change_live_state_or_rng(self):
        import random
        from adaptation import evaluate, initialize
        from town_store import dump_world
        world = self.world(); initialize(world)
        before, rng = dump_world(world), random.getstate()
        candidate = {'attack': -0.1, 'socialize': 0.1}
        first = evaluate(world, world.lonks[0], candidate)
        self.assertEqual(first, evaluate(world, world.lonks[0], candidate))
        self.assertEqual(len(first), 4)
        self.assertEqual(before, dump_world(world))
        self.assertEqual(rng, random.getstate())

    def test_gate_requires_benefit_and_rejects_harm(self):
        from adaptation import passes, valid
        old = dict(alive=1, trauma=0, population=3, welfare=0)
        good = dict(old, welfare=1)
        self.assertTrue(passes([[old, good]] * 4))
        self.assertFalse(passes([[old, old]] * 4))
        for bad in (dict(good, trauma=1), dict(good, alive=0),
                    dict(good, population=21), dict(good, welfare=float('nan'))):
            self.assertFalse(passes([[old, bad]] * 4))
        for bad in ({'attack': 0.6}, {'gate': 0.1}, {'idle': float('nan')}):
            self.assertFalse(valid(bad))

    def test_accept_persist_rollback_and_detect_tampering(self):
        from unittest.mock import patch
        from adaptation import reflect, rollback, verify
        from town_store import dump_world, load_world
        world = self.world(); lonk = world.lonks[0]
        old = dict(alive=1, trauma=2, population=3, welfare=0)
        # Controlled evaluator result tests the commit boundary; real trials above.
        with patch('adaptation.evaluate', return_value=[[old, dict(old, welfare=1)]] * 4):
            self.assertIn('accepted', reflect(world, lonk))
        self.assertEqual(lonk.behavior_policy, {'attack': -0.1, 'socialize': 0.1})
        world = load_world(dump_world(world)); lonk = world.lonks[0]
        self.assertTrue(verify(world))
        self.assertIn('restored', rollback(world, lonk))
        self.assertEqual(lonk.behavior_policy, {})
        self.assertTrue(lonk.policy_frozen)
        self.assertTrue(verify(world))
        self.assertIn('frozen', reflect(world, lonk))
        world.policy_audit[0]['reason'] = 'tampered'
        self.assertFalse(verify(world))
        with self.assertRaises(ValueError):
            reflect(world, lonk)

    def test_failed_trial_is_rejected_and_recorded(self):
        import subprocess
        from unittest.mock import patch
        from adaptation import reflect, verify
        world = self.world(); lonk = world.lonks[0]
        with patch('adaptation.evaluate', side_effect=subprocess.TimeoutExpired('trial', 8)):
            self.assertIn('rejected', reflect(world, lonk))
        self.assertEqual(lonk.behavior_policy, {})
        self.assertEqual(world.policy_audit[-1]['decision'], 'rejected')
        self.assertTrue(verify(world))

    def test_legacy_snapshot_migrates_without_reset(self):
        from adaptation import initialize
        from town_store import dump_world, load_world
        world = self.world(); name = world.lonks[0].name
        for lonk in world.lonks:
            del lonk.behavior_policy
            del lonk.policy_frozen
        world = load_world(dump_world(world)); initialize(world)
        self.assertEqual(world.lonks[0].name, name)
        self.assertEqual(world.lonks[0].trauma, 2)
        self.assertEqual(world.lonks[0].behavior_policy, {})

    def test_real_proposal_can_be_accepted_and_rolled_back(self):
        import random
        from adaptation import reflect, rollback
        random.seed(16)
        with capture_output():
            world = LonkWorld(4)
        lonk = world.lonks[0]
        lonk.trauma = 2
        lonk.emotion['anxiety'] = 80
        self.assertIn('accepted', reflect(world, lonk))
        self.assertEqual(lonk.behavior_policy['attack'], -0.1)
        self.assertIn('restored', rollback(world, lonk))
        self.assertEqual(lonk.behavior_policy, {})
