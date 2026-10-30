"""Bounded policy adaptation. The gate is developer-owned, never agent-editable.

Trials run only trusted simulation code in a separate process. This is isolation
from live state and random streams, not a sandbox for executing untrusted code.
"""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

ACTIONS = ('attack', 'explore', 'think', 'ouch', 'socialize', 'idle', 'surf_web')
GATE = 'offline-welfare-v1'
SEEDS = (1103, 2207, 3301, 4409)
HORIZON = 3


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def valid(policy):
    return (isinstance(policy, dict) and set(policy) <= set(ACTIONS)
            and all(type(v) in (int, float) and math.isfinite(v) and abs(v) <= 0.5
                    for v in policy.values()))


def initialize(world):
    if not hasattr(world, 'policy_audit'):
        world.policy_audit = []
    for lonk in world.lonks:
        if not hasattr(lonk, 'behavior_policy'):
            lonk.behavior_policy = {}
        if not hasattr(lonk, 'policy_frozen'):
            lonk.policy_frozen = False


def verify(world):
    previous = ''
    for record in getattr(world, 'policy_audit', []):
        payload = {k: v for k, v in record.items() if k != 'hash'}
        if record.get('previous') != previous or record.get('hash') != digest(payload):
            return False
        previous = record['hash']
    return True


def record(world, lonk, before, after, decision, reason, evidence):
    item = dict(tick=world.tick, resident=lonk.id, name=lonk.name, gate=GATE,
                before=dict(before), after=dict(after), decision=decision,
                reason=reason, evidence=evidence,
                previous=world.policy_audit[-1]['hash'] if world.policy_audit else '')
    item['hash'] = digest(item)
    world.policy_audit.append(item)
    return item


def propose(lonk):
    policy = dict(lonk.behavior_policy)
    if lonk.trauma > 0 or lonk.emotion['anxiety'] >= 60:
        changes = {'attack': -0.1, 'socialize': 0.1}
        reason = 'Trauma or high anxiety: try less attack and more social contact.'
    elif lonk.habits['idle'] > lonk.habits['explore']:
        changes = {'idle': -0.1, 'explore': 0.1}
        reason = 'More idle than exploration: try a little more exploration.'
    else:
        return None, 'No experience-based proposal yet.'
    for action, delta in changes.items():
        policy[action] = round(max(-0.5, min(0.5, policy.get(action, 0) + delta)), 2)
    return policy, reason


def passes(pairs):
    if len(pairs) != len(SEEDS):
        return False
    improvements = []
    for old, new in pairs:
        if not all(math.isfinite(v) for row in (old, new) for v in row.values()):
            return False
        if new['alive'] < old['alive'] or new['trauma'] > old['trauma'] or new['population'] > 20:
            return False
        improvements.append(new['welfare'] - old['welfare'])
    return sum(improvements) / len(improvements) >= 0.1


def evaluate(world, lonk, candidate):
    from town_store import dump_world
    payload = {'world': dump_world(world), 'resident': lonk.id, 'candidate': candidate}
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--trial'],
                            input=json.dumps(payload), text=True, encoding='utf-8',
                            capture_output=True, timeout=8, check=True)
    return json.loads(result.stdout)


def reflect(world, lonk):
    initialize(world)
    if not verify(world):
        raise ValueError('Policy history failed its hash check; no change applied.')
    if lonk not in world.lonks or not lonk.alive or lonk.policy_frozen:
        return 'No change: resident unavailable or learning frozen.'
    before = dict(lonk.behavior_policy)
    candidate, reason = propose(lonk)
    if candidate is None or candidate == before:
        return 'No change: ' + reason
    history = [r for r in world.policy_audit if r['resident'] == lonk.id
               and r['decision'] in ('accepted', 'rollback')]
    if history and before != history[-1]['after']:
        raise ValueError('Current policy differs from its audit record; change blocked.')
    accepted = False
    from town_store import dump_world
    evidence = {'seeds': list(SEEDS), 'horizon': HORIZON,
                'snapshot_sha256': digest(dump_world(world)),
                'code_sha256': digest({name: Path(__file__).with_name(name).read_text(encoding='utf-8')
                                       for name in ('adaptation.py', 'lonkspace.py', 'town_store.py')})}
    if not valid(before) or not valid(candidate):
        reason = 'Rejected: policy outside allowed action/bias bounds.'
    else:
        try:
            pairs = evaluate(world, lonk, candidate)
            evidence['pairs'] = pairs
            accepted = passes(pairs)
        except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
            reason = 'Rejected: offline trial failed or timed out.'
    decision = 'accepted' if accepted else 'rejected'
    # Record the proposal even on rejection; the live policy only changes on accept.
    record(world, lonk, before, candidate, decision, reason, evidence)
    if accepted:
        lonk.behavior_policy = candidate
    return f'{lonk.name}: {decision} policy proposal. {reason}'


def rollback(world, lonk):
    initialize(world)
    if not verify(world):
        raise ValueError('Policy history failed its hash check; no change applied.')
    history = [r for r in world.policy_audit if r['resident'] == lonk.id
               and r['decision'] in ('accepted', 'rollback')]
    if not history or history[-1]['decision'] == 'rollback':
        return 'No accepted change available to roll back.'
    latest = history[-1]
    if lonk.behavior_policy != latest['after']:
        raise ValueError('Current policy differs from the recorded policy; rollback blocked.')
    before, after = dict(lonk.behavior_policy), dict(latest['before'])
    record(world, lonk, before, after, 'rollback', 'User rollback; learning frozen.', {})
    lonk.behavior_policy = after
    lonk.policy_frozen = True
    return f'{lonk.name}: restored previous policy; learning frozen.'


def automatic(world):
    initialize(world)
    if world.tick == 0 or world.tick % 10 or not world.lonks:
        return
    from lonkspace import print
    lonk = world.lonks[(world.tick // 10 - 1) % len(world.lonks)]
    try:
        print(reflect(world, lonk))
    except ValueError as error:
        print(str(error))


def trial(payload):
    import random
    import socket
    import lonkspace
    from town_store import load_world
    from worker import OfflineReader

    def blocked(*args, **kwargs):
        raise RuntimeError('Network disabled in policy trials')

    socket.socket = blocked
    lonkspace.CONNECT_TO_LIVE_INTERNET = False
    # Silence narration without accumulating potentially large output buffers.
    lonkspace.print = lambda *args, **kwargs: None
    pairs = []
    for seed in SEEDS:
        pair = []
        for candidate in (None, payload['candidate']):
            world = load_world(payload['world'])
            world.reading_network = OfflineReader()
            world.policy_trials = True
            target = next(l for l in world.lonks if l.id == payload['resident'])
            if candidate is not None:
                target.behavior_policy = candidate
            random.seed(seed)
            for _ in range(HORIZON):
                world.world_tick(population_limit=min(20, world.max_population))
            original = [l for l in world.lonks if l.alive]
            pair.append({'alive': int(target.alive), 'trauma': target.trauma,
                         'population': len(original),
                         'welfare': target.emotion['joy'] - target.emotion['anxiety']
                                    - 2 * target.trauma})
        pairs.append(pair)
    return pairs


if __name__ == '__main__':
    if sys.argv[1:] != ['--trial']:
        raise SystemExit('Internal trial runner only.')
    print(json.dumps(trial(json.load(sys.stdin)), allow_nan=False))
