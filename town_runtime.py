"""Background actions for one account. Internet I/O stays outside world write locks."""
import contextlib
import json
import random
import time
import requests
from lonkspace import ReadingNetwork, MoltbookBridge, capture_output


class CachedReader(ReadingNetwork):
    def prepare(self, source='auto', topic=''):
        if source == 'auto':
            sources = ['wiki', 'nasa']
            if self.moltbook.data.get('api_key'):
                sources.append('moltbook')
            source = random.choice(sources)
        if time.time() >= self.next_fetch.get(source, 0):
            self.next_fetch[source] = time.time() + 60
            try:
                self.cache[(source, topic)] = self.fetch(source, topic)
            except requests.RequestException:
                raise ValueError(source + ': connection failed; no text learned.')
        # read() must only consume prefetched material while a transaction is held.
        for name in self.SOURCES:
            self.next_fetch[name] = max(self.next_fetch.get(name, 0), time.time() + 1)
        return source

    def read(self, lonk, source='auto', topic=''):
        for name in self.SOURCES:
            self.next_fetch[name] = max(self.next_fetch.get(name, 0), time.time() + 1)
        return super().read(lonk, source, topic)


class TownRuntime:
    def __init__(self, store):
        self.store = store
        folder = store.path.parent / 'moltbook' / store.owner_id
        self.bridge = MoltbookBridge(folder)
        self.reader = CachedReader(self.bridge)

    def message(self, text):
        with self.store.transaction() as db:
            self.store.log(db, self.store.read(db).tick, text)

    def recover(self):
        with self.store.transaction() as db:
            rows = db.execute("SELECT id FROM commands WHERE owner_id=? AND state='running'", (self.store.owner_id,)).fetchall()
            if rows:
                db.execute("UPDATE commands SET state='interrupted' WHERE owner_id=? AND state='running'", (self.store.owner_id,))
                self.store.log(db, self.store.read(db).tick,
                    'A background action was interrupted. It was not retried. For Moltbook publishing, check your profile before resolving or resubmitting.')

    def run_command(self):
        with self.store.transaction() as db:
            job = db.execute("SELECT * FROM commands WHERE owner_id=? AND state='pending' ORDER BY id LIMIT 1", (self.store.owner_id,)).fetchone()
            if not job:
                return
            db.execute("UPDATE commands SET state='running' WHERE id=?", (job['id'],))
        args = json.loads(job['args'])
        state, text = 'done', ''
        try:
            if job['kind'] == 'surf':
                with contextlib.closing(self.store.connect()) as db:
                    if not self.store.settings(db)['internet']:
                        raise ValueError('Outside reading is off. Enable it in My town first.')
                source = self.reader.prepare(args['source'], args.get('topic', ''))
                with self.store.transaction() as db, capture_output() as output:
                    world = self.store.read(db)
                    if not self.store.settings(db)['internet']:
                        raise ValueError('Outside reading was switched off; nothing learned.')
                    lonk = next((l for l in world.lonks if l.id == args['resident'] and l.alive), None)
                    if not lonk:
                        raise ValueError('That resident is no longer alive. Choose a current resident.')
                    lonk.habits['surf_web'] += 1
                    self.reader.read(lonk, source, args.get('topic', ''))
                    self.store.write(db, world)
                    text = output.getvalue()
            elif job['kind'] == 'step':
                from worker import tick_once, OfflineReader
                for _ in range(args['count']):
                    with contextlib.closing(self.store.connect()) as db:
                        settings = self.store.settings(db)
                    if not settings['paused']:
                        raise ValueError('Manual stepping stopped: the world is no longer paused.')
                    if settings['internet']:
                        self.reader.prepare()
                    tick_once(self.store, self.reader if settings['internet'] else OfflineReader(), force=True)
                text = 'Manual steps completed.'
            elif job['kind'] == 'molt':
                with capture_output() as output:
                    self.bridge.command(args['command'], self.store.load())
                text = output.getvalue()
            else:
                raise ValueError('Unknown queued action.')
        except (ValueError, KeyError, OSError) as error:
            state, text = 'failed', str(error)
        with self.store.transaction() as db:
            db.execute('UPDATE commands SET state=? WHERE id=?', (state, job['id']))
            self.store.log(db, self.store.read(db).tick, text or 'Action completed.')
            db.execute("DELETE FROM commands WHERE owner_id=? AND state!='pending' AND id NOT IN (SELECT id FROM commands WHERE owner_id=? ORDER BY id DESC LIMIT 100)", (self.store.owner_id,self.store.owner_id))

    def tick(self):
        with contextlib.closing(self.store.connect()) as db:
            settings = self.store.settings(db)
        if settings['paused']:
            return
        if settings['internet']:
            try:
                self.reader.prepare()
            except (ValueError, TypeError, KeyError) as error:
                self.message(str(error))
        from worker import tick_once, OfflineReader
        tick_once(self.store, self.reader if settings['internet'] else OfflineReader())
