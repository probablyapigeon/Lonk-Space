"""The shared town: humans and Lonks read/write one durable feed."""
import contextlib
import hmac
import os
import re
import secrets
import sqlite3
import time
import uuid
import json
from datetime import timedelta

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from town_store import Store
from lonkspace import capture_output


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

    def town():
        if not g.user:
            abort(401, 'Sign in to visit your town.')
        return store.for_user(g.user['id'])

    @app.before_request
    def protect_forms():
        with contextlib.closing(store.connect()) as db:
            g.user = current_user(db)
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
        from types import SimpleNamespace
        user = g.user
        world = SimpleNamespace(tick=0, lonks=[], lonkspace_feed=[])
        settings, logs, last_tick, pending = {}, [], None, 0
        if user:
            with contextlib.closing(store.connect()) as db:
                bound = town()
                world = bound.read(db)
                settings = bound.settings(db)
                last_tick = db.execute('SELECT last_tick FROM towns WHERE owner_id=?', (user['id'],)).fetchone()[0]
                logs = db.execute('SELECT tick,text FROM activity WHERE owner_id=? ORDER BY id DESC LIMIT 15', (user['id'],)).fetchall()[::-1]
                pending = db.execute("SELECT count(*) FROM commands WHERE owner_id=? AND state IN ('pending','running')", (user['id'],)).fetchone()[0]
        with capture_output() as report:
            if user:
                world.show_civilization_status()
        report_text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', report.getvalue())
        posts = list(reversed([p for p in world.lonkspace_feed if not p.get('hidden')]))
        page_number = max(1, request.args.get('page', 1, type=int))
        total = len(posts)
        posts = posts[(page_number-1)*20:page_number*20]
        return render_template('town.html', page=page, world=world, user=user,
                               admin=bool(user), posts=posts, page_number=page_number,
                               has_next=page_number*20 < total, total_posts=total,
                               settings=settings, logs=logs, pending=pending, status_report=report_text,
                               worker_active=bool(last_tick and time.time()-last_tick < 180),
                               **extra)

    @app.get('/')
    def home():
        return render('dashboard' if g.user else 'welcome')

    @app.get('/feed')
    def feed():
        town()
        return render('feed')

    @app.get('/thread/<post_id>')
    def thread(post_id):
        world = town().load()
        post = next((p for p in world.lonkspace_feed if p.get('id') == post_id
                     and not p.get('hidden')), None)
        if not post:
            abort(404)
        return render('thread', post=post)

    @app.get('/lonk/<lonk_id>')
    def profile(lonk_id):
        lonk = next((l for l in town().load().lonks if l.id == lonk_id), None)
        if not lonk:
            abort(404, 'This resident is no longer in your living population.')
        with capture_output() as output:
            world = lonk.world
            world.lonks = [lonk]
            world.show_lonk_details(lonk.name)
        import re as regex
        details = regex.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', output.getvalue())
        return render('profile', lonk=lonk, details=details,
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
            store.ensure_town(db, user['id'])
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
            world = town().read(db)
            if parent:
                try:
                    world.add_comment(parent, user['username'], body, 'human', user['id'])
                except ValueError:
                    abort(404)
                post_id = parent
            else:
                post_id = world.add_post(user['username'], title, body, 'human', user['id'])['id']
            town().write(db, world)
            db.execute('UPDATE users SET last_post=? WHERE id=?', (time.time(), user['id']))
        return redirect(url_for('thread', post_id=post_id))

    @app.post('/hide/<post_id>')
    def hide(post_id):
        with store.transaction() as db:
            user = current_user(db)
            world = town().read(db)
            post = next((p for p in world.lonkspace_feed if p.get('id') == post_id), None)
            if not post:
                abort(404)
            comment_id = request.form.get('comment', '')
            item = next((c for c in post['comments'] if c.get('id') == comment_id), None) if comment_id else post
            if not item:
                abort(404)
            if not user:
                abort(403)
            item['hidden'] = True
            town().write(db, world)
        flash('Hidden from the feed and future reading. Existing Lonk memories are unchanged.')
        return redirect(url_for('home'))

    @app.post('/say')
    def say():
        bound = town()
        body = request.form.get('body', '').strip()
        if not 1 <= len(body) <= 2000:
            abort(400, 'Write a message of 1–2000 characters.')
        with bound.transaction() as db, capture_output() as output:
            user = db.execute('SELECT * FROM users WHERE id=?', (g.user['id'],)).fetchone()
            if time.time() - user['last_post'] < app.config.get('POST_INTERVAL', 10):
                abort(429, 'Wait ten seconds between messages.')
            world = bound.read(db)
            lonk = next((l for l in world.lonks if l.id == request.form.get('resident') and l.alive), None)
            if not lonk:
                abort(404, 'Choose a current resident from your town.')
            post = world.add_post(user['username'], f'A conversation with {lonk.name}'[:160], body, 'human', user['id'])
            world.read_post(lonk, post, reply=True)
            bound.write(db, world)
            bound.log(db, world.tick, output.getvalue())
            db.execute('UPDATE users SET last_post=? WHERE id=?', (time.time(),user['id']))
        return redirect(url_for('thread', post_id=post['id']))

    @app.post('/settings')
    def settings():
        bound = town()
        interval = request.form.get('interval', '30', type=int)
        if interval not in (10,30,60,120):
            abort(400, 'Choose a supported clock speed.')
        with bound.transaction() as db:
            values = {'internet':request.form.get('internet') == 'on',
                      'paused':request.form.get('paused') == 'on', 'interval':interval}
            db.execute('UPDATE towns SET settings=? WHERE owner_id=?', (json.dumps(values),g.user['id']))
            bound.log(db, bound.read(db).tick, 'Town settings saved. Outside reading ' + ('enabled.' if values['internet'] else 'disabled.'))
        flash('Settings saved for your town.')
        return redirect(url_for('home'))

    @app.post('/queue/<kind>')
    def queue(kind):
        bound = town()
        args = {}
        if kind == 'surf':
            source = request.form.get('source', 'auto')
            if source not in ('auto','wiki','nasa','moltbook','replies','bacon'):
                abort(400)
            topic = request.form.get('topic','').strip()
            if len(topic) > 200:
                abort(400, 'Topic is too long.')
            args = {'source':source, 'topic':topic, 'resident':request.form.get('resident','')}
        elif kind == 'molt':
            action = request.form.get('action', '')
            if action not in ('register','status','draft','publish','verify','resolve'):
                abort(400)
            arg = request.form.get('arg','').strip()
            if len(arg) > 100 or '\n' in arg or '\r' in arg:
                abort(400)
            if action in ('publish','resolve') and request.form.get('confirm') != 'yes':
                abort(400, 'Confirm the external action first.')
            args = {'command': 'molt ' + action + (' ' + arg if arg else '')}
        elif kind == 'step':
            count = request.form.get('count',1,type=int)
            if count not in (1,5,10):
                abort(400)
            args = {'count':count}
        else:
            abort(404)
        with bound.transaction() as db:
            pending = db.execute("SELECT count(*) FROM commands WHERE owner_id=? AND state IN ('pending','running')", (g.user['id'],)).fetchone()[0]
            if pending >= 3:
                abort(429, 'Wait for your queued actions to finish.')
            if kind == 'surf':
                if not bound.settings(db)['internet']:
                    abort(400, 'Turn on outside reading in Town controls first.')
                if not any(l.id == args['resident'] and l.alive for l in bound.read(db).lonks):
                    abort(404)
            if kind == 'step' and not bound.settings(db)['paused']:
                abort(400, 'Pause your world before advancing it manually.')
            db.execute('INSERT INTO commands(owner_id,kind,args) VALUES(?,?,?)', (g.user['id'],kind,json.dumps(args)))
        flash('Queued. The result will appear in your live activity panel.')
        return redirect(url_for('home'))

    @app.get('/activity')
    def activity():
        bound = town()
        with contextlib.closing(bound.connect()) as db:
            row = db.execute('SELECT revision,last_tick FROM towns WHERE owner_id=?', (g.user['id'],)).fetchone()
            logs = db.execute('SELECT id,tick,text FROM activity WHERE owner_id=? ORDER BY id DESC LIMIT 15', (g.user['id'],)).fetchall()[::-1]
            count = db.execute("SELECT count(*) FROM commands WHERE owner_id=? AND state IN ('pending','running')", (g.user['id'],)).fetchone()[0]
            return jsonify(tick=bound.read(db).tick, revision=row['revision'], last_tick=row['last_tick'],
                           pending=count, settings=bound.settings(db), logs=[dict(x) for x in logs])

    @app.post('/password')
    def password():
        bound = town()
        old, new = request.form.get('current',''), request.form.get('new','')
        if not 12 <= len(new) <= 128 or new != request.form.get('confirm'):
            abort(400, 'New passwords must match and have 12–128 characters.')
        if not limit('password:' + g.user['id'], 10, 300):
            abort(429)
        with bound.transaction() as db:
            row = db.execute('SELECT password FROM users WHERE id=?',(g.user['id'],)).fetchone()
            if not check_password_hash(row[0],old):
                abort(400, 'Current local password not recognized.')
            db.execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(new),g.user['id']))
        flash('Your local Lonk-Space password was changed.')
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
