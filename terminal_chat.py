"""Chat with the saved website town from a separate terminal on the same computer."""
import argparse
import contextlib
import getpass
import io
import os
from pathlib import Path
import re
import sqlite3
import time

from werkzeug.security import check_password_hash
from town_store import Store

HELP = '''lonks                         List living residents and their IDs
status                        Show the saved world's report
inspect <name-or-id>           Show one resident's memories and vocabulary
say <name-or-id> <message>     Speak directly; save a town thread and Lonk reply
post <title> | <message>      Add a thread for residents to encounter later
feed                          Show the last ten visible threads and their IDs
thread <post-id>               Read a thread and its replies
reply <post-id> <message>     Reply in the same feed the website uses
help                          Show these commands
quit                          Leave chat (the world worker keeps running)
Messages here are visible in your account’s website town. Chat never advances the world clock.'''


def display(value):
    # Outside text is data, never terminal control sequences.
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(value))
    print(''.join(c for c in text if c.isprintable() or c in '\n\t'))


class ExistingStore(Store):
    def __init__(self, path):
        self.owner_id = None
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise ValueError('No saved town at ' + str(self.path) +
                             '. Run chat in the same folder as webapp.py, or use --db PATH.')
        # Never initialize a new world, even if a path points to an empty database.
        try:
            with contextlib.closing(self.connect()) as db:
                self.read(db)
                db.execute('SELECT id FROM users LIMIT 1').fetchone()
        except (sqlite3.Error, TypeError, KeyError, ValueError) as error:
            raise ValueError('This is not a readable saved website town. Nothing was reset.') from error

    def connect(self):
        db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=30)
        db.row_factory = sqlite3.Row
        return db


class TownChat:
    def __init__(self, path):
        self.store = ExistingStore(path)
        self.user_id = None

    def login(self, username, password):
        self.user_id = None
        if not re.fullmatch(r'[A-Za-z0-9_]{3,24}', username) or not 1 <= len(password) <= 128:
            raise ValueError('Username or password not recognized.')
        now = time.time()
        bucket = 'auth-name:' + username.casefold()
        allowed = False
        with self.store.transaction() as db:
            attempt = db.execute('SELECT * FROM attempts WHERE bucket=?', (bucket,)).fetchone()
            if attempt and now - attempt['started'] < 300 and attempt['count'] >= 10:
                raise ValueError('Too many login attempts. Wait five minutes.')
            if not attempt or now - attempt['started'] >= 300:
                db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,1)', (bucket, now))
            else:
                db.execute('UPDATE attempts SET count=count+1 WHERE bucket=?', (bucket,))
            user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            allowed = bool(user and check_password_hash(user['password'], password))
            if allowed:
                self.user_id = user['id']
                self.store.ensure_town(db, self.user_id)
                self.store.owner_id = self.user_id
        if not allowed:
            raise ValueError('Username or password not recognized. Use your website account.')

    @staticmethod
    def resident(world, query):
        matches = [l for l in world.lonks if l.alive and
                   (l.name.casefold() == query.casefold() or l.id == query)]
        if not matches:
            raise ValueError('No living resident matches. Use lonks for current names and IDs.')
        if len(matches) > 1:
            raise ValueError('Several residents share that name. Use the full ID from lonks.')
        return matches[0]

    def command(self, line):
        action, _, arg = line.strip().partition(' ')
        action = action.lower()
        if action in ('quit', 'exit'):
            return False
        if action in ('help', ''):
            display(HELP)
            return True
        if action in ('say', 'post', 'reply'):
            self.write(action, arg)
            return True
        world = self.store.load()
        if action == 'lonks':
            for lonk in world.lonks:
                if lonk.alive:
                    display(f'{lonk.name} | {lonk.faction} | {lonk.id}')
        elif action in ('status', 'inspect'):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                if action == 'status':
                    world.show_civilization_status()
                else:
                    lonk = self.resident(world, arg.strip())
                    # The old name-based reporter can display duplicate names; constrain its view.
                    world.lonks = [lonk]
                    world.show_lonk_details(lonk.name)
            display(output.getvalue())
        elif action == 'feed':
            for post in [p for p in world.lonkspace_feed if not p.get('hidden')][-10:]:
                display(f"[{post['id']}] {post['author']} ({post['author_type']}): {post['title']}")
        elif action == 'thread':
            post = next((p for p in world.lonkspace_feed if p['id'] == arg.strip()
                         and not p.get('hidden')), None)
            if not post:
                raise ValueError('Thread not found. Use feed to see post IDs.')
            display(f"{post['author']}: {post['title']}\n{post.get('body', '')}")
            for comment in post['comments']:
                if not comment.get('hidden'):
                    display(f"  {comment['author']}: {comment['body']}")
        else:
            raise ValueError('Unknown command. Type help. Use say <name> <message> to talk.')
        return True

    def write(self, action, arg):
        if not self.user_id:
            raise ValueError('Sign in with your website account first.')
        separator = '|' if action == 'post' else ' '
        target, found, message = arg.partition(separator)
        target, message = target.strip(), message.strip()
        if not found or not target or not 1 <= len(message) <= 2000:
            raise ValueError('Use help for command formats. Messages must have 1–2000 characters.')
        if action == 'post' and len(target) > 160:
            raise ValueError('Titles may have at most 160 characters.')
        output = io.StringIO()
        with self.store.transaction() as db:
            user = db.execute('SELECT * FROM users WHERE id=?', (self.user_id,)).fetchone()
            if not user:
                raise ValueError('Your account no longer exists. Sign in again.')
            if time.time() - user['last_post'] < 10:
                raise ValueError('Wait ten seconds between messages (shared with website posting).')
            world = self.store.read(db)
            if action == 'say':
                lonk = self.resident(world, target)
                post = world.add_post(user['username'], f'A conversation with {lonk.name}'[:160],
                                      message, 'human', user['id'])
                with contextlib.redirect_stdout(output):
                    world.read_post(lonk, post, reply=True)
                post_id = post['id']
            elif action == 'post':
                post_id = world.add_post(user['username'], target, message, 'human', user['id'])['id']
            else:
                world.add_comment(target, user['username'], message, 'human', user['id'])
                post_id = target
            self.store.write(db, world)
            db.execute('UPDATE users SET last_post=? WHERE id=?', (time.time(), user['id']))
        # Announce only after the transaction successfully commits.
        if output.getvalue():
            display(output.getvalue())
        display('Saved to the website feed. Thread ID: ' + post_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=os.environ.get('LONK_DB', 'data/town.db'),
                        help='Same database path used by webapp.py and worker.py')
    args = parser.parse_args()
    try:
        chat = TownChat(args.db)
        display('Saved town: ' + str(chat.store.path))
        display('Sign in with your website account. Password entry stays invisible.')
        for _ in range(3):
            try:
                chat.login(input('Username: ').strip(), getpass.getpass('Password: '))
                break
            except ValueError as error:
                display(error)
        else:
            return 1
        display('\nConnected to the SAME saved town. Messages appear in your account’s website town.\n' + HELP)
        while True:
            try:
                if not chat.command(input('town> ')):
                    break
            except ValueError as error:
                display(error)
            except sqlite3.OperationalError:
                display('Database unavailable or busy. No success confirmed; check the feed before retrying.')
    except (EOFError, KeyboardInterrupt):
        display('\nChat closed. Your website and worker are unaffected.')
    except (ValueError, sqlite3.Error, OSError) as error:
        display(error)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
