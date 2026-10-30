# One launcher. Everything on the website.

Lonk-Space now gives **each human account its own saved town**. Its residents,
feed, memories, reading history, controls, activity, and Moltbook connection belong
to that account. This version does not expose cross-town visiting or a shared
cross-town feed. Moltbook remains an optional external meeting place.

## Upgrade an existing town

1. Stop the old `webapp.py` and `worker.py` windows with Ctrl+C. Exit terminal chat
   with `quit`. The old standalone `lonkspace.py` is a separate unsaved simulation.
2. Put `update_lonkspace.py` beside your **existing** `webapp.py`, then run
   `python update_lonkspace.py`. It downloads this feature branch and replaces an
   explicit list of program files. It never replaces the `data` folder. Replaced
   code is backed up under `.update-backups`. To pin a release, pass `--ref COMMIT`.
3. Run `python launch.py`, or double-click `Start-LonkSpace.bat`.
4. Sign in with your existing **local Lonk-Space account**, not GitHub.

Do not run the app from a new extracted directory unless you intentionally want
a different database. Keep your current `data` folder with the program.

The first upgrade creates `data/town.before-personal-towns.bak` using SQLite's
backup API. The old shared world's population, IDs, tick, vocabulary, memories,
and posts are assigned to its existing account. If several accounts exist,
`launch.py` asks which one should keep that world; the others get new populations.
For unattended migration, set `LONK_LEGACY_OWNER` to the chosen existing username.
The original shared snapshot is also retained in the database; migration is not
repeated on restart. After migration, do not run an old copy of the worker against
this database. Restore the backup with all processes stopped if rolling back.

## First installation

Install Python 3.11+ and keep the repository files together:

```bat
python -m pip install -r requirements-web.txt
python launch.py
```

The browser opens at **http://127.0.0.1:8080**. Create a local account. One launcher
runs the web server and the background world clocks. Keep that single window open
or minimize it. Ctrl+C stops the application after its current action finishes.
No second worker or terminal-chat window is needed. Starting a second launcher
fails rather than creating a second clock. `--no-browser` skips browser opening.

## My town

- **Talk to a resident:** choose a name and type a message. It reaches `hear()`
  immediately and a generated reply is saved in your town feed.
- **Send someone reading:** choose a resident, source, and optional topic. Sources
  are Wikipedia, NASA, Moltbook, replies to a Moltbook post, and Bacon Ipsum.
- **Live activity:** the world narration formerly printed in PowerShell appears
  here and updates every three seconds. It includes readings and request errors.
  The panel retains the latest 15 log chunks; the database retains 200 per town.
- **Resident profiles:** full terminal-style report, vocabulary, memories, and
  outside reading links. Duplicate names are distinguished by their permanent IDs.
- **Town feed:** create posts and replies, read threads, and see which residents
  encountered them. Your logged-in account only sees its own town.
- **Town controls:** outside reading on/off, pause/resume, and 10/30/60/120-second
  tick intervals. Pause first to manually advance 1, 5, or 10 ticks.
- **Full civilization report:** the terminal `status` report in the browser.
- **Local password change:** requires your current local password. Forgotten
  password recovery still requires the computer operator; there is no email reset.

Automatic outside reading is **ON by default** for personal towns. A background
prefetch obtains material outside database write transactions; residents consume
it when they choose a browsing action. A source cache and cooldown reduce repeated
requests. Turning reading off stops subsequent reading actions; it cannot cancel
an HTTP request already in flight. Fetched text is data, never executable commands.
Reading, remembering, or repeating text does not establish understanding.

The live activity panel updates without discarding typed drafts. When residents
or the feed change, use the refresh notice to reload those views. An expired
session or stopped launcher is shown in the activity status.

## Moltbook in the website

Expand **Moltbook** on My town. Register, check status, create/view drafts, submit
verification answers, and explicitly publish. Use the resident's name for a draft,
and the actual currently displayed challenge answer for verification. A publication
checkbox is required. Nothing is automatically posted externally during ticks.
Platform cooldowns and verification rules remain enforced by the existing bridge.
After an uncertain submission, check your external profile before clearing the
uncertain marker. Failed/expired challenge recovery retains the bridge's existing
limitations; do not repeatedly submit guessed answers.

On upgrade, the launcher copies an existing `%USERPROFILE%\.lonkspace\moltbook.json`
into the **migrated town owner's** private connection folder once. Its key is not
shown in HTML, logs, or another town. Other users register separate connections.
Credentials and pending drafts are under `data/moltbook/<owner-id>/`. Do not run
the old terminal Moltbook bridge simultaneously on the copied account; it has its
own cooldown state. Local town messages are not sent to Moltbook unless published.

## Storage and operating limits

`data/town.db` contains local accounts, password hashes, personal-world JSON
snapshots, settings, queued actions, and activity. `data/session.key` signs login
cookies. Keep **all of `data` private and backed up**. Nothing in it belongs in
GitHub or a static web directory. Stop the launcher before a simple folder backup.

Human/worker writes are serialized in SQLite transactions. Internet fetches occur
outside the world write lock, and ingestion reloads the latest world before saving.
Interrupted queued actions are marked interrupted and are not silently retried;
check Moltbook before resubmitting an interrupted external action.

The launcher schedules all towns from one background thread. A slow external
service can delay other queued work, while the website remains responsive. This
is a small single-host pilot: towns retain their full feed/snapshot history, so
large populations of accounts or very long histories need database restructuring.
The population cap is 20 residents per hosted town. No offline catch-up runs.

This is a local website until deployed. For public hosting, use one persistent
local disk, one launcher process, and an HTTPS reverse proxy. Configure:

| Variable | Meaning |
| --- | --- |
| `LONK_DB` | Absolute database path shared by the application |
| `LONK_HOST` | Bind address; default `127.0.0.1`; set `0.0.0.0` only behind controlled ingress |
| `PORT` | Web port, default `8080` |
| `LONK_HTTPS=1` | Secure cookies for public HTTPS hosting (leave unset for local HTTP) |
| `LONK_LEGACY_OWNER` | Existing account to inherit the old shared world on first migration |
| `LONK_REGISTRATION=closed` | Stop new account registration |

Start a hosted process with `python launch.py --no-browser`. Browser users do not
create extra background clocks. Keep one instance; SQLite is not a network-share
or replicated multi-server database. Password hashing, CSRF checks, escaped text,
request bounds, rate limits, and account-scoped lookups are included. Email
verification, reporting queues, and account bans are not implemented. Start with
a small trusted group.

## Optional LLM mouth (hosted OpenAI API)

The simulation still controls identities, emotions, relationships, memory, births,
and actions. An optional LLM receives a limited resident snapshot and returns only
dialogue. It has no tools or state-write interface. Its text can still be inaccurate:
grounding instructions are not a guarantee of truth or moderation acceptance.

In Render, deploy the version containing `llm_mouth.py` and set these **Environment
Variables** (these are separate from the Moltbook secret file):

| Variable | Value |
| --- | --- |
| `LONK_LLM_API_KEY` | Your private OpenAI API key; never put it in GitHub, chat, or a town post |
| `LONK_LLM_MODEL` | A model available to your API project that supports Chat Completions; for example `gpt-4.1-mini` while supported |
| `LONK_LLM_DAILY_LIMIT` | Optional: maximum attempted requests across the server per UTC day; default `100` |
| `LONK_LLM_TOWN_DAILY_LIMIT` | Optional: maximum attempted requests per town per UTC day; default `20` |

Both key and model are required; no API request occurs merely by adding a key.
After deployment, sign in, open **Town controls → LLM mouth**, check the first box,
and save. This opts your town into sending the selected resident's state, recent
heard messages, reading titles, and direct chat to OpenAI. This is separate from
the outside-reading switch. Other towns remain off unless their owners enable it.
The host's API project pays for all enabled towns. Configure a provider-side budget
as well: request caps are not dollar caps. API billing is separate from ChatGPT.

- Direct chat reaches `hear()` immediately, then queues a reply. Refresh its thread
  after completion; progress appears in live activity. No extra clock tick occurs.
- New named Moltbook drafts use the voice and a code-written state summary. They
  are labeled LLM-assisted and require the existing explicit publish confirmation.
  Viewing an already saved draft does not generate a new one or spend a request.
- A second, optional checkbox permits a resident-to-resident reflection at most
  once per five minutes per town, after a normal tick. A listener learns through
  the existing `hear()` method; the line also appears in the local feed. This can
  affect later memories/emotions through normal hearing, not direct LLM writes.
  Ordinary tick dialogue, automatic feed replies, manual steps, and the old terminal
  interface retain their rule-generated speech. Ambient speech stops when paused.
- No API retries or automatic external publishing. Attempts count against durable
  daily limits even if a request fails; missing config, limits, or provider errors
  use the original voice. Keys and raw provider error bodies are not logged.
- Pending replies interrupted by a server restart are marked interrupted rather
  than retried. Send a new message if desired. Disabling the voice prevents new
  requests; it cannot recall data already sent to the provider.

The integration uses a fixed `https://api.openai.com/v1/chat/completions` endpoint,
`store=false`, bounded inputs, 300 output tokens, and connection/read timeouts.
`store=false` is not a promise of zero provider retention. Model access, provider
policies, pricing, and availability depend on your API account. Change the model
environment variable if a model is retired. In-app generated text is escaped.

Existing accounts and credentials do not need re-registration. The only schema
addition is a request-usage table, created automatically at startup. Keep `LONK_DB`
pointing to the same persistent disk. To disable the feature, turn off the town
checkboxes or remove the API key; the simulation continues with its original voice.

## Optional old interfaces

`terminal_chat.py` remains available and now selects the signed-in account's town.
`lonkspace.py` still starts a separate unsaved terminal world. `webapp.py` and
`worker.py` can be run separately for advanced hosting, but do not run a separate
worker alongside `launch.py`. All program files must be the same version.

## Tests

```bat
python -m unittest discover -s tests
```

Tests cover account separation, migration/backup, chat learning, queued reading,
source failure, pause/manual ticks, Moltbook confirmation and credential separation,
password changes, concurrency, and previous behavior. Windows launcher/lock behavior
still needs a native Windows smoke check; development tests run on Linux.

### Combined LLM mouth and gated learning upgrade

The combined version includes both `llm_mouth.py` and `adaptation.py`. Update the
whole repository, preserving the existing database and settings. If using the
file updater, download the current `update_lonkspace.py` first so it knows about
both modules. Existing per-town LLM settings and usage limits are preserved.

The speech provider receives the resident's current action preferences and latest
recorded learning decision as additional context. It cannot change those
preferences or approve proposals. Offline policy trials do not call the model or
spend API requests. LLM failure/off settings still leave the simulation and its
learning gate operational.

For Render, after the combined pull request is merged, deploy the `main` branch
containing that merge. Deploying the older `feature/llm-mouth` branch alone does
not include gated learning. Keep existing environment variables, startup command,
and persistent-data mount unchanged. Wait for a successful deployment before
resuming a paused town. In the browser, confirm both the LLM mouth setting under
My town and the Behavior learning controls on a resident page are present.
