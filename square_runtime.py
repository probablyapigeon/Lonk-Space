"""Shared-square clock and bounded public speech, using each owner's LLM consent."""
import random
import time
from lonkspace import capture_output, generate_speech
from llm_mouth import Mouth, Speech, configured
from square import SQUARE_ID


def reply(actor_store, args):
    square = actor_store.for_user(SQUARE_ID)
    world = square.load()
    lonk = next((l for l in world.lonks if l.id == args['resident']
                 and l.visit_token == args.get('visit_token')), None)
    post = next((p for p in world.lonkspace_feed if p['id'] == args['post']), None)
    if not post:
        return 'Square reply cancelled: thread no longer available.'
    speech = None
    if lonk and not post.get('hidden'):
        speech = Mouth(actor_store.for_user(lonk.visit_owner)).say(lonk, world, post['body'])
    with square.transaction() as db:
        current = square.read(db)
        target = next((p for p in current.lonkspace_feed if p['id'] == args['post']), None)
        resident = next((l for l in current.lonks if l.id == args['resident']
                         and l.visit_token == args.get('visit_token')), None)
        if not target:
            return 'Square reply cancelled: thread no longer available.'
        target['reply_pending'] = False
        if not speech or not resident or target.get('hidden'):
            square.write(db, current)
            return 'Square reply cancelled: visitor went home or thread was hidden.'
        owner = actor_store.for_user(resident.visit_owner)
        if speech.engine == 'llm' and not owner.settings(db).get('llm'):
            speech = Speech(generate_speech(lonk=resident), 'rules')
        comment = current.add_comment(target['id'], resident.name, speech.text, author_id=resident.id)
        comment['speech_engine'] = speech.engine
        comment['context_tick'] = world.tick
        square.write(db, current)
    # The content is public, but do not copy it to the requester's private memory.
    return f'{resident.name} replied in the shared square. {speech.note}'


class SquareRuntime:
    def __init__(self, store):
        self.store = store

    def recover(self):
        pass  # Public replies are queued under the requesting account's worker.

    def run_command(self):
        pass

    def message(self, text):
        with self.store.transaction() as db:
            self.store.log(db, self.store.read(db).tick, text)

    def tick(self):
        from worker import tick_once, OfflineReader
        tick_once(self.store, OfflineReader())
        self.ambient()

    def ambient(self):
        if not configured():
            return
        with self.store.transaction() as db:
            world = self.store.read(db)
            eligible = [l for l in world.lonks if self.store.for_user(l.visit_owner).settings(db).get('llm')
                        and self.store.for_user(l.visit_owner).settings(db).get('llm_ambient')]
            if not eligible:
                return
            key = 'square_ambient'
            row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            if row and time.time() - float(row[0]) < 300:
                return
            db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', (key, str(time.time())))
            lonk = random.choice(eligible)
        speech = Mouth(self.store.for_user(lonk.visit_owner)).say(
            lonk, world, purpose='brief public-square reflection to another visitor')
        if speech.engine != 'llm':
            return
        with self.store.transaction() as db, capture_output():
            current = self.store.read(db)
            speaker = next((l for l in current.lonks if l.id == lonk.id and l.visit_token == lonk.visit_token), None)
            settings = self.store.for_user(lonk.visit_owner).settings(db)
            if not speaker or not settings.get('llm') or not settings.get('llm_ambient'):
                return
            listeners = [l for l in current.lonks if l.id != speaker.id]
            speaker.speak(speech.text, target=random.choice(listeners) if listeners else None)
            post = current.add_post(speaker.name, f'{speaker.name} reflects in the square', speech.text, author_id=speaker.id)
            post['speech_engine'] = 'llm'
            post['context_tick'] = world.tick
            self.store.write(db, current)
