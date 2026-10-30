"""Authenticated shared-space routes; private-town endpoints remain isolated."""
import contextlib
import json
import re
import time
from flask import abort, flash, g, redirect, render_template, request, url_for
from lonkspace import capture_output
from square import SQUARE_ID, CAPACITY, visit, return_home


def register_square(app, store):
    def signed_in():
        if not g.user:
            abort(401, 'Sign in to join the shared square.')

    def moderator():
        return bool(g.user and app.config['ADMIN_USER'] and
                    g.user['username'].casefold() == app.config['ADMIN_USER'])

    def may_hide(item):
        return moderator() or (item.get('author_type') == 'human' and item.get('author_id') == g.user['id'])

    def pace(db):
        last = db.execute('SELECT last_post FROM users WHERE id=?', (g.user['id'],)).fetchone()[0]
        if time.time() - last < app.config.get('POST_INTERVAL', 10):
            abort(429, 'Wait ten seconds between messages.')
        db.execute('UPDATE users SET last_post=? WHERE id=?', (time.time(), g.user['id']))

    def page(post_id=None, resident_id=None):
        signed_in()
        with contextlib.closing(store.connect()) as db:
            world = store.for_user(SQUARE_ID).read(db)
            home = store.for_user(g.user['id']).read(db)
            logs = db.execute('SELECT text FROM activity WHERE owner_id=? ORDER BY id DESC LIMIT 5', (SQUARE_ID,)).fetchall()[::-1]
        post = next((p for p in world.lonkspace_feed if p['id'] == post_id and not p.get('hidden')), None) if post_id else None
        resident = next((l for l in world.lonks if l.id == resident_id), None) if resident_id else None
        if (post_id and not post) or (resident_id and not resident):
            abort(404, 'This conversation or visitor is no longer here.')
        details = ''
        if resident:
            with capture_output() as output:
                world.show_lonk_details(resident.name)
            details = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', output.getvalue())
        number = max(1, request.args.get('page', 1, type=int))
        posts = list(reversed([p for p in world.lonkspace_feed if not p.get('hidden')]))
        return render_template('square.html', world=world, home=home, user=g.user,
                               posts=posts[(number-1)*20:number*20], page_number=number,
                               has_next=len(posts) > number*20, post=post, resident=resident,
                               details=details, may_hide=may_hide, capacity=CAPACITY, logs=logs)

    @app.get('/square')
    def square_home():
        return page()

    @app.get('/square/thread/<post_id>')
    def square_thread(post_id):
        return page(post_id=post_id)

    @app.get('/square/lonk/<resident_id>')
    def square_profile(resident_id):
        return page(resident_id=resident_id)

    @app.post('/square/visit')
    def square_visit():
        signed_in()
        if request.form.get('confirm') != 'yes':
            abort(400, 'Confirm that new square conversations will be shared with other accounts.')
        try:
            count = visit(store, g.user['id'], g.user['username'], request.form.get('resident', 'all'))
        except ValueError as error:
            abort(400, str(error))
        flash(f'{count} Lonks are visiting. Their home places and private history are saved.')
        return redirect(url_for('square_home'))

    @app.post('/square/return')
    def square_return():
        signed_in()
        try:
            count = return_home(store, g.user['id'], request.form.get('resident', 'all'))
        except ValueError as error:
            abort(400, str(error))
        flash(f'{count} Lonks returned home with their new square experiences.')
        return redirect(url_for('square_home'))

    @app.post('/square/post')
    def square_post():
        signed_in()
        title, body = request.form.get('title', '').strip(), request.form.get('body', '').strip()
        parent = request.form.get('parent', '')
        if not 1 <= len(body) <= 2000 or (not parent and not 1 <= len(title) <= 160):
            abort(400, 'Use a message of 1–2000 characters and a title of 1–160 characters.')
        bound = store.for_user(SQUARE_ID)
        with store.transaction() as db:
            pace(db)
            world = bound.read(db)
            if parent:
                try:
                    world.add_comment(parent, g.user['username'], body, 'human', g.user['id'])
                except ValueError:
                    abort(404)
                post_id = parent
            else:
                post_id = world.add_post(g.user['username'], title, body, 'human', g.user['id'])['id']
            bound.write(db, world)
        return redirect(url_for('square_thread', post_id=post_id))

    @app.post('/square/hide/<post_id>')
    def square_hide(post_id):
        signed_in()
        bound = store.for_user(SQUARE_ID)
        with store.transaction() as db:
            world = bound.read(db)
            post = next((p for p in world.lonkspace_feed if p['id'] == post_id), None)
            if not post:
                abort(404)
            comment_id = request.form.get('comment')
            item = next((c for c in post['comments'] if c['id'] == comment_id), None) if comment_id else post
            if item is None:
                abort(404)
            if not may_hide(item):
                abort(403, 'Only the author or site moderator can hide this item.')
            item['hidden'] = True
            bound.write(db, world)
        flash('Hidden. Words already learned by visiting Lonks remain in their memories.')
        return redirect(url_for('square_home'))

    @app.post('/square/say')
    def square_say():
        signed_in()
        body = request.form.get('body', '').strip()
        if not 1 <= len(body) <= 2000:
            abort(400)
        bound = store.for_user(SQUARE_ID)
        with store.transaction() as db, capture_output():
            pace(db)
            world = bound.read(db)
            lonk = next((l for l in world.lonks if l.id == request.form.get('resident')), None)
            if lonk is None:
                abort(404)
            pending = db.execute("SELECT count(*) FROM commands WHERE owner_id=? AND state IN ('pending','running')", (g.user['id'],)).fetchone()[0]
            if pending >= 3:
                abort(429, 'Wait for your queued messages to finish.')
            post = world.add_post(g.user['username'], f'A square conversation with {lonk.name}'[:160], body, 'human', g.user['id'])
            world.read_post(lonk, post, reply=False)
            post['reply_pending'] = True
            db.execute('INSERT INTO commands(owner_id,kind,args) VALUES(?,?,?)',
                       (g.user['id'], 'square_say', json.dumps({'resident': lonk.id, 'post': post['id'], 'visit_token': lonk.visit_token})))
            bound.write(db, world)
        return redirect(url_for('square_thread', post_id=post['id']))

    @app.post('/square/policy/<resident_id>')
    def square_policy(resident_id):
        signed_in()
        from adaptation import reflect, rollback
        action = request.form.get('action')
        if action not in ('reflect', 'rollback', 'resume'):
            abort(400)
        bound = store.for_user(SQUARE_ID)
        with store.transaction() as db:
            world = bound.read(db)
            lonk = next((l for l in world.lonks if l.id == resident_id), None)
            if not lonk or lonk.visit_owner != g.user['id']:
                abort(403, 'Only the owner can manage this visitor’s learning.')
            if action == 'resume':
                lonk.policy_frozen = False
                message = 'Learning resumed.'
            else:
                try:
                    message = (reflect if action == 'reflect' else rollback)(world, lonk)
                except ValueError as error:
                    abort(400, str(error))
            bound.write(db, world)
        flash(message)
        return redirect(url_for('square_profile', resident_id=resident_id))
