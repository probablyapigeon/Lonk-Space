"""The shared town: humans and Lonks read/write one durable feed."""
import contextlib
import hmac
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import timedelta

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from town_store import Store


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=16384, MAX_FORM_PARTS=12,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('LONK_HTTPS') == '1',
                      PERMANENT_SESSION_LIFETIME=timedelta(days=7),
                      ADMIN_USER=os.environ.get('LONK_ADMIN', '').casefold())
    if config:
        app.config.update(config)
    store = Store(app.config.get('DATABASE'))
    secret_path = store.path.parent / 'session.key'
    if not app.config.get('SECRET_KEY'):
        # Atomic creation, shared across restarts and web processes.
        try:
            with open(secret_path, 'x', encoding='ascii') as f:
                os.chmod(secret_path, 0o600)
                f.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = secret_path.read_text(encoding='ascii').strip()
        if len(app.config['SECRET_KEY']) < 32:
            raise RuntimeError('Session key is incomplete; stop the server and inspect session.key.')
    app.extensions['town'] = store

    def current_user(db):
        return db.execute('SELECT id,username FROM users WHERE id=?',
                          (session.get('uid', ''),)).fetchone()

    def is_admin(user):
        return bool(user and app.config['ADMIN_USER'] and
                    user['username'].casefold() == app.config['ADMIN_USER'])

    @app.before_request
    def protect_forms():
        session.setdefault('csrf', secrets.token_hex(32))
        if request.method == 'POST':
            given = request.form.get('csrf', '')
            if not hmac.compare_digest(given, session['csrf']):
                abort(400, 'This form expired. Reload the page and try again.')

    @app.after_request
    def headers(response):
        response.headers['Content-Security-Policy'] = "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        if app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    def limit(bucket, maximum, seconds):
        now = time.time()
        with store.transaction() as db:
            db.execute('DELETE FROM attempts WHERE started < ?', (now - 3600,))
            row = db.execute('SELECT * FROM attempts WHERE bucket=?', (bucket,)).fetchone()
            if not row or now - row['started'] >= seconds:
                db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,1)', (bucket, now))
                return True
            if row['count'] >= maximum:
                return False
            db.execute('UPDATE attempts SET count=count+1 WHERE bucket=?', (bucket,))
            return True

    def render(page='feed', **extra):
        with contextlib.closing(store.connect()) as db:
            world = store.read(db)
            user = current_user(db)
            last_tick = db.execute('SELECT last_tick FROM world WHERE id=1').fetchone()[0]
        posts = [p for p in world.lonkspace_feed if not p.get('hidden')]
        page_number = max(1, request.args.get('page', 1, type=int))
        posts = list(reversed(posts))
        total = len(posts)
        posts = posts[(page_number-1)*20:page_number*20]
        return render_template('town.html', page=page, world=world, user=user,
                               admin=is_admin(user), posts=posts, page_number=page_number,
                               has_next=page_number*20 < total, total_posts=total,
                               worker_active=bool(last_tick and time.time()-last_tick < 180),
                               **extra)

    @app.get('/')
    def home():
        return render()

    @app.get('/thread/<post_id>')
    def thread(post_id):
        world = store.load()
        post = next((p for p in world.lonkspace_feed if p.get('id') == post_id
                     and not p.get('hidden')), None)
        if not post:
            abort(404)
        return render('thread', post=post)

    @app.get('/lonk/<lonk_id>')
    def profile(lonk_id):
        lonk = next((l for l in store.load().lonks if l.id == lonk_id), None)
        if not lonk:
            abort(404, 'This resident is no longer in the living population.')
        return render('profile', lonk=lonk,
                      words=sorted(lonk.vocabulary.items(), key=lambda x: -x[1])[:20])

    @app.route('/<action>', methods=['GET', 'POST'])
    def account(action):
        if action not in ('login', 'register'):
            abort(404)
        if request.method == 'GET':
            return render(action)
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        # Count all attempts; never store submitted passwords or trust forwarded IP headers.
        if not limit('auth-ip:' + (request.remote_addr or 'unknown'), 20, 300):
            abort(429, 'Too many account attempts. Try again in five minutes.')
        if not limit('auth-name:' + username.casefold()[:24], 10, 300):
            abort(429, 'Too many account attempts. Try again in five minutes.')
        if not re.fullmatch(r'[A-Za-z0-9_]{3,24}', username) or not 12 <= len(password) <= 128:
            flash('Use a 3–24 character username (letters, numbers, _) and a 12–128 character password.')
            return render(action), 400
        with store.transaction() as db:
            if action == 'register':
                if os.environ.get('LONK_REGISTRATION', 'open') != 'open':
                    abort(403, 'New registrations are closed.')
                try:
                    db.execute('INSERT INTO users(id,username,password,created) VALUES(?,?,?,?)',
                               (uuid.uuid4().hex, username, generate_password_hash(password), time.time()))
                except sqlite3.IntegrityError:
                    flash('That username is unavailable.')
                    return render(action), 400
            user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            if not user or not check_password_hash(user['password'], password):
                flash('Username or password not recognized.')
                return render(action), 401
            session.clear()
            session['uid'] = user['id']
            session['csrf'] = secrets.token_hex(32)
            session.permanent = True
        return redirect(url_for('home'))

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('home'))

    @app.post('/post')
    def post():
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        parent = request.form.get('parent', '')
        if not 1 <= len(body) <= 2000 or (not parent and not 1 <= len(title) <= 160):
            abort(400, 'Write a message of 1–2000 characters and a title of 1–160 characters.')
        with store.transaction() as db:
            user = current_user(db)
            if not user:
                abort(401, 'Sign in before posting.')
            last = db.execute('SELECT last_post FROM users WHERE id=?', (user['id'],)).fetchone()[0]
            if time.time() - last < app.config.get('POST_INTERVAL', 10):
                abort(429, 'Give the town a moment. You can post once every ten seconds.')
            world = store.read(db)
            if parent:
                try:
                    world.add_comment(parent, user['username'], body, 'human', user['id'])
                except ValueError:
                    abort(404)
                post_id = parent
            else:
                post_id = world.add_post(user['username'], title, body, 'human', user['id'])['id']
            store.write(db, world)
            db.execute('UPDATE users SET last_post=? WHERE id=?', (time.time(), user['id']))
        return redirect(url_for('thread', post_id=post_id))

    @app.post('/hide/<post_id>')
    def hide(post_id):
        with store.transaction() as db:
            user = current_user(db)
            world = store.read(db)
            post = next((p for p in world.lonkspace_feed if p.get('id') == post_id), None)
            if not post:
                abort(404)
            comment_id = request.form.get('comment', '')
            item = next((c for c in post['comments'] if c.get('id') == comment_id), None) if comment_id else post
            if not item:
                abort(404)
            if not user or not (is_admin(user) or (item.get('author_type') == 'human' and item.get('author_id') == user['id'])):
                abort(403)
            item['hidden'] = True
            store.write(db, world)
        flash('Hidden from the feed and future reading. Existing Lonk memories are unchanged.')
        return redirect(url_for('home'))

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    @app.errorhandler(429)
    def friendly_error(error):
        return render('error', error=error), error.code

    return app


if __name__ == '__main__':
    from waitress import serve
    print('Lonk-Space: http://127.0.0.1:8080 — start worker.py in another terminal.')
    serve(create_app(), host=os.environ.get('LONK_HOST', '127.0.0.1'),
          port=int(os.environ.get('PORT', '8080')), threads=4,
          max_request_body_size=16384)
