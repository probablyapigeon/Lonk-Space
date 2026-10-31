"""Background actions for one account. Internet I/O stays outside world write locks."""
import contextlib
import json
import random
import time
import requests
from lonkspace import ReadingNetwork, MoltbookBridge, capture_output
from llm_mouth import Mouth, Speech


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
            except requests.HTTPError as error:
                status = error.response.status_code if error.response is not None else 'unknown'
                hint = ' Try the exact article title.' if source == 'wiki' and status == 404 else ''
                raise ValueError(f'{source}: source returned HTTP {status}; no text learned.' + hint)
            except requests.Timeout:
                raise ValueError(source + ': request timed out; no text learned. Try again after the cooldown.')
            except requests.RequestException:
                raise ValueError(source + ': connection failed; no text learned.')
        elif (source, topic) not in self.cache:
            import math
            wait = math.ceil(self.next_fetch[source] - time.time())
            raise ValueError(f'{source}: wait {wait} seconds before requesting a new topic; no text learned.')
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
        self.mouth = Mouth(store)

    def message(self, text):
        with self.store.transaction() as db:
            self.store.log(db, self.store.read(db).tick, text)

    def recover(self):
        with self.store.transaction() as db:
            rows = db.execute("SELECT id,kind,args FROM commands WHERE owner_id=? AND state='running'", (self.store.owner_id,)).fetchall()
            if rows:
                db.execute("UPDATE commands SET state='interrupted' WHERE owner_id=? AND state='running'", (self.store.owner_id,))
                world = self.store.read(db)
                for row in rows:
                    if row['kind'] == 'say':
                        post_id = json.loads(row['args']).get('post')
                        for post in world.lonkspace_feed:
                            if post['id'] == post_id:
                                post['reply_pending'] = False
                                post['reply_interrupted'] = True
                self.store.write(db, world)
                from square import SQUARE_ID
                square_store = self.store.for_user(SQUARE_ID)
                public = square_store.read(db)
                for row in rows:
                    if row['kind'] == 'square_say':
                        post_id = json.loads(row['args']).get('post')
                        for post in public.lonkspace_feed:
                            if post['id'] == post_id:
                                post['reply_pending'] = False
                                post['reply_interrupted'] = True
                square_store.write(db, public)
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
            if job['kind'] == 'square_say':
                from square_runtime import reply
                text = reply(self.store, args)
            elif job['kind'] == 'say':
                text = self.reply(args)
            elif job['kind'] == 'surf':
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
                    learned = self.reader.read(lonk, source, args.get('topic', ''))
                    if not learned:
                        state = 'no_change'
                    self.store.write(db, world)
                    text = output.getvalue()
            elif job['kind'] == 'policy':
                from adaptation import initialize, reflect, rollback
                with self.store.transaction() as db:
                    world = self.store.read(db)
                    initialize(world)
                    lonk = next((l for l in world.lonks if l.id == args['resident'] and l.alive), None)
                    if lonk is None:
                        raise ValueError('That resident is no longer alive.')
                    if args['action'] == 'resume':
                        lonk.policy_frozen = False
                        text = 'Policy learning resumed.'
                    else:
                        text = (reflect if args['action'] == 'reflect' else rollback)(world, lonk)
                    self.store.write(db, world)
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
                parts = args['command'].split(maxsplit=2)
                with contextlib.closing(self.store.connect()) as db:
                    use_mouth = self.store.settings(db).get('llm')
                if use_mouth and len(parts) == 3 and parts[1] == 'draft':
                    text = self.draft(parts[2])
                else:
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

    def reply(self, args):
        world = self.store.load()
        lonk = next((l for l in world.lonks if l.id == args['resident'] and l.alive), None)
        post = next((p for p in world.lonkspace_feed if p['id'] == args['post']), None)
        if not post:
            return 'Reply cancelled: thread no longer exists.'
        speech = self.mouth.say(lonk, world, post['body']) if lonk and not post.get('hidden') else None
        # Reload after the request: never overwrite intervening chat, ticks, or settings.
        with self.store.transaction() as db:
            current = self.store.read(db)
            target = next((p for p in current.lonkspace_feed if p['id'] == args['post']), None)
            resident = next((l for l in current.lonks if l.id == args['resident'] and l.alive), None)
            if not target:
                return 'Reply cancelled: thread no longer exists.'
            target['reply_pending'] = False
            if not speech or not resident or target.get('hidden'):
                self.store.write(db, current)
                return 'Reply cancelled: resident or visible thread is no longer available.'
            if speech.engine == 'llm' and not self.store.settings(db).get('llm'):
                from lonkspace import generate_speech
                speech = Speech(generate_speech(lonk=resident), 'rules', 'LLM switched off; generated response discarded.')
            comment = current.add_comment(target['id'], resident.name, speech.text, author_id=resident.id)
            comment['speech_engine'] = speech.engine
            comment['context_tick'] = world.tick
            self.store.write(db, current)
        return f'{resident.name} [{speech.engine}]: {speech.text}\n{speech.note}'

    def draft(self, name):
        world = self.store.load()
        lonk = next((l for l in world.lonks if l.alive and l.name.casefold() == name.casefold()), None)
        if not lonk:
            raise ValueError('No living Lonk with that name.')
        speech = self.mouth.say(lonk, world, purpose='dispatch for human review')
        # Status facts are supplied by code, not invented by the language model.
        content = (f'Simulated character: {lonk.name}\nFaction: {lonk.faction}\n'
                   f'World tick: {world.tick}\nJob: {lonk.job}\n'
                   f'Joy: {lonk.emotion["joy"]:.0f}/100; anxiety: {lonk.emotion["anxiety"]:.0f}/100\n\n'
                   f'{speech.text}\n\n'
                   + ('LLM-assisted dialogue grounded in a simulated Lonk state. ' if speech.engine == 'llm'
                      else 'Rule-generated dialogue from a simulated Lonk. ')
                   + 'Character speech may be inaccurate; this is not a factual report.')
        self.bridge.data['draft'] = {'submolt_name':'general',
            'title':f'{lonk.name}: town diary, tick {world.tick}', 'content':content}
        self.bridge.save()
        return ('DRAFT ONLY — destination: m/general\n' + self.bridge.data['draft']['title']
                + '\n' + content + '\n' + speech.note
                + '\nReview before explicitly publishing. Nothing was posted.')

    def ambient(self):
        if not self.mouth.ambient_due():
            return
        world = self.store.load()
        living = [l for l in world.lonks if l.alive]
        if not living:
            return
        lonk = random.choice(living)
        speech = self.mouth.say(lonk, world, purpose='brief reflection to a fellow resident')
        if speech.engine != 'llm':
            self.message(speech.note)
            return
        with self.store.transaction() as db, capture_output() as output:
            settings = self.store.settings(db)
            if settings['paused'] or not settings.get('llm') or not settings.get('llm_ambient'):
                return
            current = self.store.read(db)
            speaker = next((l for l in current.lonks if l.id == lonk.id and l.alive), None)
            if not speaker:
                return
            listeners = [l for l in current.lonks if l.alive and l.id != speaker.id]
            listener = random.choice(listeners) if listeners else None
            speaker.speak(speech.text, target=listener)
            post = current.add_post(speaker.name, f'{speaker.name} reflects', speech.text, author_id=speaker.id)
            post['speech_engine'] = 'llm'
            post['context_tick'] = world.tick
            self.store.write(db, current)
            self.store.log(db, current.tick, '[LLM voice]\n' + output.getvalue())

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
        self.ambient()
