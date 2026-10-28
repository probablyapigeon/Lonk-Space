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

- **Restarting creates a fresh population.** Inhabitants are not yet saved between sessions.
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
