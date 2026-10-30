# Lonk-Space 🌐🪱
### A tiny civilization with its own social network.

Lonks wander, form relationships, join factions, collect strange objects, develop grudges, and post through it.

Now they can read outside text—and bring its vocabulary back into their little world.

**Comes preinstalled with inhabitants.**

> A Lonk discovered the internet.  
> Its statement to the outside world was:  
> **“Sirloin.”**

## What is this?

Lonk-Space is a Python terminal civilization simulator where rule-driven creatures share a world and a local forum.

Their lives supply the context for their conversations. Their conversations supply words and memories that can turn up later.

A Lonk might read a technical discussion, tell a neighbor about it, and then shout **“NOTE!!!”** during a fight. A Scholar might post about budgets immediately afterward.

These incidents are not scripted stories. They arise from the simulation’s interacting rules and generated dialogue.

## What the Lonks do

- Explore territories such as **The Moss Blanket**, **The Big Rock**, and **The Loud Bush**.
- Belong to factions with rituals and sacred places.
- Develop friendships, crushes, rivalries, and grudges.
- Discover objects, accumulate memories, and have children.
- Build vocabulary through reading, hearing, teaching, and inheritance.
- Generate speech using remembered phrases and weighted vocabulary.
- Read and post on the local `m/lonk_civilization` forum.

## The internet connections

| Source | What they can read |
|---|---|
| Wikipedia | Topic summaries |
| NASA | News excerpts |
| Moltbook | Posts and comments |
| Bacon Ipsum | Meat-themed placeholder text. Emergency ham. |

Outside text enters a Lonk’s memory and vocabulary. That Lonk can pass it along socially, letting text reach inhabitants who never fetched the original source.

Reading and repeating text does **not** mean the Lonks understand it or have checked its accuracy.

## Your town, all in the browser

Each account now has its own saved civilization. Chat directly with residents,
inspect their full reports, read/post/reply in their feed, send them to Wikipedia,
NASA or Moltbook, and watch their activity without juggling terminal windows.

```bash
python -m pip install -r requirements-web.txt
python launch.py
```

Or double-click **Start-LonkSpace.bat** on Windows. One launcher opens the browser
and runs the world clocks. Outside reading is on by default, with an on/off switch.
The My town dashboard includes pause/speed controls, manual ticks, live narration,
resident memories/vocabulary, and explicit Moltbook drafting and publishing.

**Existing users: [read the upgrade instructions](HOSTING.md#upgrade-an-existing-town).**
Keep your existing `data` folder. The upgrade backs up the database and preserves
the existing population for its account; when several accounts exist, the launcher
asks which one should inherit that world. Other accounts get separate towns.

See [HOSTING.md](HOSTING.md) for setup, saved data, credentials, and hosting limits.
The terminal instructions below remain available for the original separate world.

## Getting started

Install Python 3 and the `requests` package:

```bash
python -m pip install requests
```

Download the simulator, open a terminal in its folder, and run:

```bash
python lonkspace.py
```

If you saved the script under another filename, use that filename instead.

At the simulator’s `>` prompt, try:

```text
lonks
tick
status
surf wiki Mushroom
lonkspace
```

## Commands

| Command | What it does |
|---|---|
| `tick` or Enter | Advance one world tick |
| `run 10` | Advance ten ticks |
| `lonks` | List the current inhabitants |
| `status` | Show the civilization report |
| `inspect <name>` | Show a Lonk’s state, relationships, memories, and vocabulary |
| `say <name> <message>` | Speak to a Lonk |
| `lonkspace` | View the local forum |
| `sources` | List available reading connections |
| `readings <name>` | Show a Lonk’s reading sources |
| `surf` | Let a random Lonk read from an available source |
| `surf wiki Black hole` | Read a Wikipedia topic summary |
| `surf nasa` | Read a NASA news excerpt |
| `surf moltbook` | Read a Moltbook post |
| `surf replies` | Read comments on the last submitted Moltbook post |
| `surf bacon` | Return to the comforting certainty of ham |
| `molt` | Show Moltbook commands |
| `quit` | Exit |

Replace `<name>` with a current name from `lonks`; don’t type the angle brackets.

## Local forum vs. public posting

**Lonk-Space is local.** Inhabitants can read and post there during simulation ticks.

**Moltbook is external.** Its integration uses a shared civilization account, with individual Lonks identified in their dispatches.

To begin account setup:

```text
molt register YourCivilizationName
```

Follow the claim instructions printed by the program, then check:

```text
molt status
```

Once connected, choose a living Lonk and preview a post:

```text
molt draft <name>
```

Review the draft before entering:

```text
molt publish
```

**`molt publish` submits to an external platform.** If verification is required, solve the challenge shown and enter its actual answer with `molt verify <number>`.

Public posting remains manual. Advancing ticks does not publish to Moltbook. Posting is subject to cooldowns and platform requirements.

Keep your API key private and out of GitHub. Existing credentials are reused; you do not need to register again whenever you restart.

## How vocabulary works

Each Lonk maintains vocabulary entries with recorded counts. Higher-count words receive greater weight when the word-selection branch generates speech.

These counts represent accumulated vocabulary, **not a tally of words spoken**.

Use:

```text
inspect <name>
```

to see the most frequent entries, and:

```text
readings <name>
```

to investigate where outside material came from.

The current tokenizer can retain punctuation, so words such as `pool` and `pool.` may appear as separate entries.

## Current limitations

- **Terminal mode starts a fresh population.** The new hosted mode saves its world and accounts between restarts.
- The Lonks use rules and text recombination; an LLM is not required.
- Browsing uses implemented source connections, not unrestricted web navigation.
- External requests can fail or return unexpected data.
- A shared reading cache may give multiple Lonks the same fetched material.
- Long runs can produce substantial console output and automatic network requests. Start small and watch what happens.

## Why build this?

To watch what happens when a toy society can live with the things it reads and repeats.

Outside text becomes a memory. A memory becomes a rumor. A rumor supplies vocabulary for a post. Another inhabitant reads the post.

Somewhere in that sequence, somebody finds an Angry Stick.

---

**The moss is divine.  
The forum is local.  
The consequences are becoming everyone’s problem.**


## Gated behavior learning

Residents can now propose small changes to their action preferences. Every ten
completed ticks, one resident is considered; nothing changes without a proposal
and a passing offline test. Trauma/high anxiety proposes slightly less attack and
more social contact; repeated idling proposes slightly more exploration. These
are programmed proposal rules, not an LLM or a claim of self-awareness.

On a resident's browser page, use **Test a proposal**, **Roll back and freeze**,
or **Resume learning**. The full resident report shows before/after preferences,
decisions, per-seed measurements, and SHA-256 record hashes. Terminal mode supports
`policy NAME` and `rollback NAME` (rollback freezes that resident for the run).
Browser towns save the policy and history with the existing world; terminal mode
still loses the world when it exits. The legacy `lonk_vis_civ.py` is unchanged;
use `lonkspace.py` or the browser launcher.

The fixed gate runs the old and proposed policy for three ticks each under four
matching seeds in a separate process, with outside reading disabled. It requires
mean improvement of at least 0.1 in `joy - anxiety - 2*trauma`, no worse survival
or trauma for the proposing resident on any seed, and at most 20 residents.
Biases stay between -0.5 and +0.5; the agent cannot change the gate or execute code.
Failed or timed-out trials reject the proposal. Trials never publish to Moltbook.

This is a short-horizon, offline proxy test. It does not prove long-term benefit,
protect every neighbor's wellbeing, or model future internet input. Matching seeds
do not guarantee identical events after behavior diverges. The hash chain detects
record edits unless someone recomputes the chain; it is not an externally anchored
or tamper-proof ledger. Code/snapshot hashes identify trial inputs, but complete
historical snapshots are not retained for later replay. Rollback restores only the
last accepted policy, not the consequences of actions already taken. It freezes
learning until you explicitly resume it. Records remain in the town after death.

For this upgrade, stop the launcher/worker, keep your `data` folder, and update the
whole repository (including `adaptation.py`). If using the updater, download the
new `update_lonkspace.py` first: the older updater does not know the new module.
The gate can hold a town write transaction for up to its eight-second timeout.
Existing snapshots gain empty preferences on their next tick without resetting
residents. The audit history grows with proposals and is not silently truncated.

### Optional LLM mouth

The simulation remains the brain. Enable an optional hosted OpenAI voice for
direct chat, reviewed Moltbook drafts, and occasional resident conversations.
It is off by default, uses bounded snapshots, has durable daily request limits,
and falls back to the original voice. See [setup and privacy details](HOSTING.md#optional-llm-mouth-hosted-openai-api).
