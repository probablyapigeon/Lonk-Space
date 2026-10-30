"""Shared square and atomic visits. Private memory never travels to public state."""
import copy
import uuid
import json

from lonkspace import Lonk, LonkWorld, capture_output
from adaptation import initialize, record, verify

SQUARE_ID = '__shared_square__'
CAPACITY = 100
# Numeric state and generated identity only. No memory, vocabulary, social history,
# catchphrase, personal inventory, reading history, or arbitrary object attributes.
TRAVEL_STATE = ('state', 'emotion', 'personality', 'habits', 'trauma', 'generation',
                'mutations', 'wealth', 'job', 'faction', 'faith', 'behavior_policy',
                'policy_frozen')


def ensure_square(db):
    if db.execute('SELECT 1 FROM towns WHERE owner_id=?', (SQUARE_ID,)).fetchone():
        return
    from town_store import dump_world
    with capture_output():
        world = LonkWorld(0)
    world.public_square = True
    world.max_population = CAPACITY
    world.lonkspace_feed[0].update(title='Welcome to the shared town square!',
                                  body='Everyone can meet here. Private towns stay private.')
    settings = dict(internet=False, paused=False, interval=30, llm=False, llm_ambient=False)
    db.execute('INSERT INTO towns VALUES(?,?,0,NULL,?)',
               (SQUARE_ID, dump_world(world), json.dumps(settings)))


def visit(store, owner_id, username, resident='all'):
    home_store, public_store = store.for_user(owner_id), store.for_user(SQUARE_ID)
    with store.transaction() as db:
        home, public = home_store.read(db), public_store.read(db)
        initialize(home); initialize(public)
        if not verify(home) or not verify(public):
            raise ValueError('Policy history failed its check; visit cancelled.')
        chosen = [l for l in home.lonks if l.alive and (resident == 'all' or l.id == resident)]
        if not chosen:
            raise ValueError('No matching residents at home. They may already be visiting.')
        if len(public.lonks) + len(chosen) > CAPACITY:
            raise ValueError('The square is full for this group. Nobody was moved; try a smaller group later.')
        parked = getattr(home, 'visiting_lonks', [])
        public_ids = {l.id for l in public.lonks}
        if any(l.id in public_ids for l in chosen):
            raise ValueError('A visit is already active; no duplicate created.')
        for original in chosen:
            visitor = Lonk(original.name, public)
            for attr in TRAVEL_STATE:
                if hasattr(original, attr):
                    setattr(visitor, attr, copy.deepcopy(getattr(original, attr)))
            visitor.id = original.id
            visitor.name = f'{original.name} · @{username}/{original.id[:4]}'
            visitor.age, visitor.lifespan = original.age, original.lifespan
            from lonkspace import FACTION_RELIGIONS
            visitor.religion = copy.deepcopy(FACTION_RELIGIONS[visitor.faction])
            visitor.visit_token = uuid.uuid4().hex
            visitor.visit_owner = owner_id
            visitor.visit_owner_name = username
            visitor.visit_name = original.name
            # Keep all private context on the parked original, never in the square.
            record(public, visitor, {}, visitor.behavior_policy, 'arrival',
                   'Owner brought this resident to the square.', {})
            public.lonks.append(visitor)
            home.lonks.remove(original)
            parked.append(original)
        home.visiting_lonks = parked
        for lonk in home.lonks:
            if lonk.rival in chosen:
                lonk.rival = None
        home_store.write(db, home)
        public_store.write(db, public)
        home_store.log(db, home.tick, f'{len(chosen)} residents are visiting the shared square.')
        return len(chosen)


def return_home(store, owner_id, resident='all'):
    home_store, public_store = store.for_user(owner_id), store.for_user(SQUARE_ID)
    with store.transaction() as db:
        home, public = home_store.read(db), public_store.read(db)
        initialize(home); initialize(public)
        if not verify(home) or not verify(public):
            raise ValueError('Policy history failed its check; return cancelled.')
        chosen = [l for l in public.lonks if getattr(l, 'visit_owner', None) == owner_id
                  and (resident == 'all' or l.id == resident)]
        if not chosen:
            raise ValueError('No matching visitors owned by you.')
        parked = {l.id: l for l in getattr(home, 'visiting_lonks', [])}
        if any(l.id not in parked for l in chosen):
            raise ValueError('Home record missing; no resident was moved.')
        for visitor in chosen:
            original = parked[visitor.id]
            before = dict(original.behavior_policy)
            for attr in TRAVEL_STATE:
                setattr(original, attr, copy.deepcopy(getattr(visitor, attr)))
            record(home, original, before, original.behavior_policy, 'return',
                   'Returned with square experiences and current policy.',
                   {'square_history_hash': public.policy_audit[-1]['hash']})
            # Preserve private context; add only new experiences from this visit.
            for event in visitor.memory['events']:
                event = copy.deepcopy(event)
                event['source_space'] = 'square'
                original.memory['events'].append(event)
            for word, count in visitor.vocabulary.items():
                original.vocabulary[word] += count
            for name, score in visitor.relationships.items():
                original.relationships[name] += score
            original.inventory.extend(visitor.inventory)
            original.world = home
            home.lonks.append(original)
            home.visiting_lonks.remove(original)
            public.lonks.remove(visitor)
        for lonk in public.lonks:
            if lonk.rival in chosen:
                lonk.rival = None
        home_store.write(db, home)
        public_store.write(db, public)
        home_store.log(db, home.tick, f'{len(chosen)} residents returned from the shared square.')
        return len(chosen)
