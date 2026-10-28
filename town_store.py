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


class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get('LONK_DB', 'data/town.db')).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with contextlib.closing(self.connect()) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS world (
                    id INTEGER PRIMARY KEY CHECK(id=1), snapshot TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0, last_tick REAL);
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password TEXT NOT NULL, created REAL NOT NULL, last_post REAL NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS attempts (
                    bucket TEXT PRIMARY KEY, started REAL NOT NULL, count INTEGER NOT NULL);
            ''')
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM world WHERE id=1').fetchone():
                db.execute('INSERT INTO world(id,snapshot) VALUES(1,?)',
                           (dump_world(LonkWorld(5)),))
            db.commit()
        os.chmod(self.path, 0o600)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

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
        return load_world(db.execute('SELECT snapshot FROM world WHERE id=1').fetchone()[0])

    def write(self, db, world):
        db.execute('UPDATE world SET snapshot=?, revision=revision+1 WHERE id=1',
                   (dump_world(world),))

    def load(self):
        with contextlib.closing(self.connect()) as db:
            return self.read(db)
