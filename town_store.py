"""Transactional single-world storage. No pickle or executable snapshot format."""
import contextlib
import json
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

from lonkspace import Lonk, LonkWorld, LonkDynamics, MythSystem

CLASSES = {c.__name__: c for c in (Lonk, LonkWorld, LonkDynamics, MythSystem)}


def dump_world(world):
    objects, seen = [], {}

    def encode(value):
        if type(value).__name__ in CLASSES and type(value) in CLASSES.values():
            key = id(value)
            if key not in seen:
                seen[key] = len(objects)
                record = {'class': type(value).__name__, 'attrs': None}
                objects.append(record)
                record['attrs'] = {k: encode(v) for k, v in vars(value).items()
                                   if k != 'reading_network'}
            return {'ref': seen[key]}
        if isinstance(value, defaultdict):
            factory = 'int' if value.default_factory is int else 'float'
            return {'defaultdict': factory, 'items': encode(dict(value))}
        if isinstance(value, dict):
            return {'dict': [[encode(k), encode(v)] for k, v in value.items()]}
        if isinstance(value, (list, tuple, set)):
            return {type(value).__name__: [encode(v) for v in value]}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise TypeError(f'Unsupported world value: {type(value).__name__}')

    root = encode(world)
    return json.dumps({'version': 1, 'root': root, 'objects': objects}, ensure_ascii=False)


def load_world(text):
    data = json.loads(text)
    if data['version'] != 1:
        raise ValueError('Unsupported saved-world version; preserve the database.')
    objects = [CLASSES[r['class']].__new__(CLASSES[r['class']]) for r in data['objects']]

    def decode(value):
        if not isinstance(value, dict):
            return value
        if 'ref' in value:
            return objects[value['ref']]
        if 'defaultdict' in value:
            return defaultdict(int if value['defaultdict'] == 'int' else float,
                               decode(value['items']))
        if 'dict' in value:
            return {decode(k): decode(v) for k, v in value['dict']}
        for tag, constructor in (('list', list), ('tuple', tuple), ('set', set)):
            if tag in value:
                return constructor(decode(v) for v in value[tag])
        raise ValueError('Invalid snapshot value')

    for obj, record in zip(objects, data['objects']):
        obj.__dict__.update({k: decode(v) for k, v in record['attrs'].items()})
    return decode(data['root'])


DEFAULT_SETTINGS = {'internet': True, 'paused': False, 'interval': 30,
                    'llm': False, 'llm_ambient': False}


class Store:
    def __init__(self, path=None, owner_id=None):
        self.path = Path(path or os.environ.get('LONK_DB', 'data/town.db')).resolve()
        self.owner_id = owner_id
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with contextlib.closing(self.connect()) as db:
            legacy = db.execute("SELECT 1 FROM sqlite_master WHERE name='world'").fetchone()
            migrated = db.execute("SELECT 1 FROM sqlite_master WHERE name='towns'").fetchone()
            if legacy and not migrated:
                backup = self.path.with_suffix('.before-personal-towns.bak')
                if not backup.exists():
                    with contextlib.closing(sqlite3.connect(backup)) as dest:
                        db.backup(dest)
                    os.chmod(backup, 0o600)
                users = db.execute('SELECT id,username FROM users ORDER BY created,id').fetchall()
                selected = os.environ.get('LONK_LEGACY_OWNER', '')
                if len(users) > 1 and not selected:
                    raise ValueError('Multiple existing accounts: start launch.py to choose who keeps the current town.')
                if selected and not any(u['username'].casefold() == selected.casefold() for u in users):
                    raise ValueError('LONK_LEGACY_OWNER must name an existing account.')
            db.executescript("""
                CREATE TABLE IF NOT EXISTS world (
                    id INTEGER PRIMARY KEY CHECK(id=1), snapshot TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0, last_tick REAL);
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password TEXT NOT NULL, created REAL NOT NULL, last_post REAL NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS attempts (
                    bucket TEXT PRIMARY KEY, started REAL NOT NULL, count INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS towns (
                    owner_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0, last_tick REAL,
                    settings TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS llm_usage (
                    day TEXT NOT NULL, scope TEXT NOT NULL, count INTEGER NOT NULL,
                    PRIMARY KEY(day,scope));
                CREATE TABLE IF NOT EXISTS activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id TEXT NOT NULL,
                    tick INTEGER NOT NULL, text TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id TEXT NOT NULL,
                    kind TEXT NOT NULL, args TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending');
            """)
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM world WHERE id=1').fetchone():
                from lonkspace import capture_output
                with capture_output():
                    world = LonkWorld(5)
                db.execute('INSERT INTO world(id,snapshot) VALUES(1,?)', (dump_world(world),))
            users = db.execute('SELECT id,username FROM users ORDER BY created,id').fetchall()
            selected = os.environ.get('LONK_LEGACY_OWNER', '').casefold()
            users = sorted(users, key=lambda u: u['username'].casefold() != selected) if selected else users
            for user in users:
                self.ensure_town(db, user['id'])
            db.commit()
        os.chmod(self.path, 0o600)

    def for_user(self, owner_id):
        bound = object.__new__(Store)
        bound.path, bound.owner_id = self.path, owner_id
        return bound

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def ensure_town(self, db, owner_id):
        if db.execute('SELECT 1 FROM towns WHERE owner_id=?', (owner_id,)).fetchone():
            return
        if not db.execute('SELECT 1 FROM users WHERE id=?', (owner_id,)).fetchone():
            raise ValueError('Unknown town owner.')
        legacy = db.execute("SELECT value FROM meta WHERE key='legacy_owner'").fetchone()
        if not legacy:
            record = db.execute('SELECT snapshot,last_tick,revision FROM world WHERE id=1').fetchone()
            snapshot, last_tick, revision = record['snapshot'], record['last_tick'], record['revision']
            db.execute("INSERT INTO meta VALUES('legacy_owner',?)", (owner_id,))
        else:
            from lonkspace import capture_output
            with capture_output():
                snapshot = dump_world(LonkWorld(5))
            last_tick, revision = None, 0
        db.execute('INSERT INTO towns VALUES(?,?,?,?,?)',
                   (owner_id, snapshot, revision, last_tick, json.dumps(DEFAULT_SETTINGS)))

    def resolved_owner(self, db):
        if getattr(self, 'owner_id', None):
            return self.owner_id
        row = db.execute("SELECT value FROM meta WHERE key='legacy_owner'").fetchone()
        return row[0] if row else None

    @contextlib.contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @contextlib.contextmanager
    def world_change(self):
        with self.transaction() as db:
            world = self.read(db)
            yield world
            self.write(db, world)

    def read(self, db):
        owner = self.resolved_owner(db)
        row = db.execute('SELECT snapshot FROM towns WHERE owner_id=?', (owner,)).fetchone() if owner else db.execute('SELECT snapshot FROM world WHERE id=1').fetchone()
        if not row:
            raise ValueError('Town not found.')
        return load_world(row[0])

    def write(self, db, world):
        owner = self.resolved_owner(db)
        if owner:
            db.execute('UPDATE towns SET snapshot=?,revision=revision+1 WHERE owner_id=?',
                       (dump_world(world), owner))
        else:
            db.execute('UPDATE world SET snapshot=?,revision=revision+1 WHERE id=1', (dump_world(world),))

    def load(self):
        with contextlib.closing(self.connect()) as db:
            return self.read(db)

    def log(self, db, tick, text):
        import re
        owner = self.resolved_owner(db)
        if not owner or not text.strip():
            return
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
        text = ''.join(c for c in text if c.isprintable() or c in '\n\t')[-18000:]
        db.execute('INSERT INTO activity(owner_id,tick,text) VALUES(?,?,?)', (owner,tick,text))
        db.execute('DELETE FROM activity WHERE owner_id=? AND id NOT IN (SELECT id FROM activity WHERE owner_id=? ORDER BY id DESC LIMIT 200)', (owner,owner))

    def settings(self, db):
        row = db.execute('SELECT settings FROM towns WHERE owner_id=?', (self.resolved_owner(db),)).fetchone()
        return {**DEFAULT_SETTINGS, **json.loads(row[0])} if row else dict(DEFAULT_SETTINGS)
