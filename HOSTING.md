# Your inhabited website

This adds a browser town square to the existing simulation. Human posts and replies
enter the same feed the Lonks read. When a resident encounters a thread, `hear()`
updates their memory and vocabulary. They may reply using the existing speech
rules. Thread pages record recent Lonk readers; resident profiles link memories
back to their source threads. Reading is probabilistic, not an instant chatbot
response. Replies are word recombinations, not proof of comprehension.

## Start on Windows

Download this branch's complete repository ZIP and extract it. Keep the files and
`templates` / `static` folders together. Open Command Prompt in that folder:

```bat
python -m pip install -r requirements-web.txt
python webapp.py
```

Open **http://127.0.0.1:8080** in your browser. Choose **Move in**, create a human
account, and write a post. Passwords must have at least 12 characters.

Open a **second Command Prompt in the same folder** and run:

```bat
python worker.py
```

The worker advances one tick, then waits 30 seconds. Refresh the website to see
new activity. Click a thread to see readers and replies; click a resident to see
vocabulary and memories. Encounters are random, so no particular post or reply
is guaranteed to be read immediately.

Stop either process with Ctrl+C. Restart using the same commands and folder:
the same residents, human accounts, posts, replies, and completed ticks return.
There is no automatic catch-up while the worker is stopped.

## What gets saved

`data/town.db` holds accounts, password hashes, and a versioned JSON snapshot of
the whole world. `data/session.key` signs login cookies. Keep the entire `data`
folder private and backed up. Neither belongs in GitHub. The database contains
human messages and Lonk memories; assume posted text may be repeated by Lonks.

All mutations use SQLite transactions. The worker and website load the latest
snapshot under a write lock, preventing lost posts or partially saved ticks.
Object references (including rivals), sets, and vocabulary counters are restored.
A failed tick rolls back; an unreadable save fails instead of creating a new world.

`python lonkspace.py` still starts the original **separate, unsaved terminal world**.
It does not connect to the website's world. Existing terminal populations cannot
be recovered after they have already been closed.

## Terminal chat with the SAME saved residents

Keep the website and worker running. In a **third terminal in the same folder**:

```bat
python terminal_chat.py
```

Sign in with your website username and password. Password typing is invisible.
Use `lonks` for current names, then `say Hogsprag hello friend` (substitute a
living name). `say` directly delivers your message through `hear()`, generates
a Lonk reply, and saves both in a **public thread on your town website**. It does
not advance ticks. This explicit encounter is different from a normal feed post,
which residents encounter randomly. Replies use the simulation's word generator.

Other commands:

```text
status
inspect Hogsprag
post A thought about moss | The moss remembers.
feed
thread POST_ID
reply POST_ID Hello neighbors.
help
quit
```

Use full IDs from `lonks` if names repeat, and post IDs from `feed` for threads.
Posting shares the website's ten-second cooldown. All writes use the same database
transactions as the worker and website. `quit` closes only your chat.

The command refuses to create a world if it cannot find an existing saved town.
It accesses your **local database**, not a remote website: use the same `LONK_DB`
environment variable as the server, or `python terminal_chat.py --db PATH`.
Do not copy a server database to another computer expecting live synchronization.
No new dependencies, server restart, or database migration are needed. Existing
installations can add just `terminal_chat.py` next to `webapp.py` and keep their
current `data` folder. `python lonkspace.py` remains the separate original world.

## World clock

```bat
python worker.py --interval 60
python worker.py --once
```

Run only one worker per database. A second worker is rejected by an OS file lock;
a crash releases the lock automatically. Browser visits never advance time or
create additional worlds. Hosted births respect `world.max_population` (20 by
default); ordinary terminal simulation behavior is preserved.

The worker has outside reading **off by default**. To opt into Wikipedia/NASA:

```bat
python worker.py --internet
```

The hosted worker does not load your personal Moltbook key or publish externally.
The existing terminal Moltbook commands remain available in the terminal version.
Outside requests run during a tick and can temporarily delay writes to the town.

## Put it on a server

This first version targets a small, single-server community, not a multi-server
social network. Use a Python 3.11+ host with a persistent local disk and the ability
to supervise two processes:

- Web process: `python webapp.py`
- World process: `python worker.py`

Both processes must use the same absolute `LONK_DB` path on the same host. Mount
persistent storage there; disposable container storage will lose the world when
replaced. Do not run replicas of the worker or share SQLite over a network drive.

Terminate HTTPS at your hosting platform or reverse proxy. Configure:

| Environment variable | Meaning |
| --- | --- |
| `LONK_DB` | Absolute database path, e.g. `/var/lib/lonkspace/town.db` |
| `LONK_HOST` | Web bind address; default `127.0.0.1`. Use `0.0.0.0` only behind the host's controlled ingress. |
| `PORT` | Web port; default `8080` |
| `LONK_HTTPS=1` | Require HTTPS for login cookies; enable for public hosting, not local HTTP |
| `LONK_ADMIN` | Existing human username allowed to hide any post or reply |
| `LONK_REGISTRATION=closed` | Disable new accounts (existing users can still sign in) |

Create your owner account privately before setting `LONK_ADMIN` and exposing the
site, so nobody else can register the intended owner name. Restart the web process
after changing configuration. Authors can hide their own content; the configured
owner can also hide Lonk content. Hidden content stops appearing in the feed and
future thread reads, but it is not erased from earlier memories or the database.

The application includes password hashing, CSRF checks, escaped text, cookie
protections, request-size limits, account-attempt limits, and posting cooldowns.
It has **no email verification, password recovery, reporting queue, or account-ban
interface yet**. Begin with a small trusted group. Back up the database before
updates; stop both processes before copying the `data` folder for a simple backup.
The feed is paginated, but snapshots retain its history; large histories need a
future migration to separate post tables. Do not expose `data` as a static folder.

## Checks

```bat
python -m unittest discover -s tests
```

Tests cover post → hearing → reply → restart, authentication and CSRF, escaped
HTML, hide permissions, cooldowns, concurrent writes, rollback, object references,
single-worker locking, and the hosted population limit. Browser visits do not
create extra worlds. Windows-specific locking should be smoke-tested on Windows;
automated execution during development was on Linux.
