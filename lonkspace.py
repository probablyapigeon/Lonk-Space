import requests
import random
import math
import time
import re
from collections import defaultdict

# ============================================================
# GLOBAL ENGINE CONFIGURATION
# ============================================================
# Set to True to read Wikipedia, NASA, Moltbook, and optional Bacon Ipsum.
# Set to False to disable web requests.
CONNECT_TO_LIVE_INTERNET = True 

# ============================================================
# VISUAL CONFIGURATION
# ============================================================
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PURPLE = '\033[95m'
    PINK = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Faction colors
FACTION_COLORS = {
    "Moss Goblins": Colors.GREEN,
    "Shiny Seekers": Colors.YELLOW,
    "Chaos Choir": Colors.PURPLE,
    "Bonk Battalion": Colors.RED,
    "Mushroom Union": Colors.CYAN
}

# Emoji for factions
FACTION_EMOJI = {
    "Moss Goblins": "🍃",
    "Shiny Seekers": "✨",
    "Chaos Choir": "🎭",
    "Bonk Battalion": "⚔️",
    "Mushroom Union": "🍄"
}

# ========== NAME GENERATION ==========
NAME_START = [
    "Scr", "Blib", "Bonk", "Grub", "Snar", "Plib", "Krub", "Yib", "Trun", "Mog",
    "Wib", "Frub", "Glo", "Spro", "Nib", "Zag", "Dro", "Clum", "Bree", "Hog",
    "Lon", "Lonk", "Blor", "Snif", "Grib", "Plon", "Drib", "Yon", "Tru", "Mof"
]

NAME_END = [
    "blo", "bble", "dunk", "glo", "fip", "wunk", "sprag", "mop", "doodle",
    "snip", "gunk", "wobble", "florp", "snorf", "tunk", "zibble", "crunk", "k"
]

def generate_name():
    name = random.choice(NAME_START) + random.choice(NAME_END)
    if name == "Lonkk":
        return generate_name()
    return name

def split_syllables(name):
    return re.findall(r'[bcdfghjklmnpqrstvwxyz]*[aeiou]+', name, re.I) or [name]

def colored(text, color):
    return f"{color}{text}{Colors.END}"

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*50}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(50)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*50}{Colors.END}\n")

def print_faction(text, faction):
    color = FACTION_COLORS.get(faction, Colors.WHITE)
    emoji = FACTION_EMOJI.get(faction, "")
    return f"{color}{emoji} {text}{Colors.END}"

# ========== SPEECH ==========
def generate_speech(context=None, lonk=None):
    if not lonk:
        return random.choice(["...", "hmm.", "I am."])

    fragments = []
    words = []

    if lonk.gossip:
        for _, _, msg in lonk.gossip:
            if msg and 3 <= len(msg.split()) <= 5:
                fragments.append(msg)
    if lonk.memory.get("player_interactions"):
        for msg in lonk.memory["player_interactions"]:
            if msg and 3 <= len(msg.split()) <= 5:
                fragments.append(msg)
    if lonk.memory.get("events"):
        for e in lonk.memory["events"]:
            if e.get("message") and 3 <= len(e["message"].split()) <= 5:
                fragments.append(e["message"])

    # FIX: Only include words with count > 0
    words = [w for w in lonk.vocabulary.keys() if len(w) > 2 and lonk.vocabulary[w] > 0]

    if fragments and random.random() < 0.5:
        phrase = random.choice(fragments)
        if words and random.random() < 0.3:
            word = random.choice(words)
            phrase = f"{phrase} {word}" if random.random() < 0.5 else f"{word} {phrase}"
        return phrase.capitalize() + random.choice(['.', '!', '?', '...'])

    if words:
        num_words = random.randint(1, min(8, len(words)))
        weights = [lonk.vocabulary[w] for w in words]
        selected = random.choices(words, weights=weights, k=num_words)

        connectors = ["", "and", "but", "or", "then", "also", "maybe"]
        result = []
        for i, word in enumerate(selected):
            result.append(word)
            if i < len(selected) - 1 and random.random() < 0.4:
                result.append(random.choice(connectors))

        phrase = ' '.join(result).capitalize()

        if context == "fight":
            phrase = phrase.rstrip('.') + random.choice(['!', '!!', '!!!'])
        elif context == "pain":
            phrase = phrase.rstrip('.') + random.choice(['!!', '!!!', '...'])
        elif not phrase.endswith(('!', '?', '.')):
            phrase += random.choice(['.', '!', '?', '...'])

        return phrase

    return random.choice([
        "Dedicated to Edgar, Neo, Fork, and Family.",
        "The void... speaks.",
        "Chaos... reigns.",
        "I... am.",
        "Thoughts... form."
    ])

# ========== MYTH & LEGEND SYSTEM ==========
class MythSystem:
    def __init__(self):
        self.myths = []
        self.legend_counter = 0

    def add_myth(self, creator, content, myth_type="tale"):
        self.legend_counter += 1
        myth = {
            "id": self.legend_counter,
            "creator": creator,
            "content": content,
            "type": myth_type,
            "believers": set([creator]),
            "age": 0,
            "variations": [content]
        }
        self.myths.append(myth)
        return myth

    def evolve_myth(self, myth_id, new_content):
        for myth in self.myths:
            if myth["id"] == myth_id:
                myth["variations"].append(new_content)
                myth["content"] = new_content
                myth["age"] += 1
                return

# ========== RELIGION SYSTEM ==========
FACTION_RELIGIONS = {
    "Moss Goblins": {
        "name": "The Soft Faith",
        "deity": "The Great Moss",
        "ritual": "communing with dampness",
        "sacred_item": "Moss Cube",
        "beliefs": ["moss is divine", "stillness is virtue", "dampness is sacred"]
    },
    "Shiny Seekers": {
        "name": "Church of the Gleam",
        "deity": "The Shiny One",
        "ritual": "polishing shiny objects",
        "sacred_item": "Shiny Rock",
        "beliefs": ["shiny = power", "hoard everything", "light is divine"]
    },
    "Chaos Choir": {
        "name": "The Loud Faith",
        "deity": "The Great Noise",
        "ritual": "screaming at the sky",
        "sacred_item": "Screaming Pebble",
        "beliefs": ["chaos is divine", "loud = good", "randomness is sacred"]
    },
    "Bonk Battalion": {
        "name": "The Holy Bonk",
        "deity": "The Bonk God",
        "ritual": "bonking sacred rocks",
        "sacred_item": "Angry Stick",
        "beliefs": ["bonk is love", "bonk is law", "violence is temporary"]
    },
    "Mushroom Union": {
        "name": "The Fungal Faith",
        "deity": "The Great Spore",
        "ritual": "spreading spores",
        "sacred_item": "Forbidden Berry",
        "beliefs": ["fungus is life", "decay is sacred", "the circle continues"]
    }
}

# ========== TERRITORIES ==========
TERRITORIES = {
    "The Moss Blanket": {"vibe": "soft, damp, emotionally supportive", "bonus": {"wisdom": +5}, "faction_bonus": "Moss Goblins", "emoji": "🟩"},
    "The Loud Bush": {"vibe": "rustles aggressively for no reason", "bonus": {"curiosity": +4}, "faction_bonus": "Chaos Choir", "emoji": "🟫"},
    "The Shiny Pit": {"vibe": "glimmers ominously, hums in F#", "bonus": {"loyalty": +3}, "faction_bonus": "Shiny Seekers", "emoji": "✨"},
    "The Big Rock": {"vibe": "immovable, judgmental, slightly warm", "bonus": {"courage": +3}, "faction_bonus": "Bonk Battalion", "emoji": "🪨"},
    "Chaos Choir's sacred ground": {"vibe": "sacred ground", "bonus": {"power": +5}, "faction_bonus": "Chaos Choir", "emoji": "🎭"},
    "The Mushroom Grove": {"vibe": "spores float in the air", "bonus": {"wisdom": +3, "anxiety": -2}, "faction_bonus": "Mushroom Union", "emoji": "🍄"}
}

# ========== ITEMS ==========
ITEMS = {
    "Shiny Pebble": {"effect": {"loyalty": +3}, "vibe": "glimmers with suspicious enthusiasm", "value": 1, "emoji": "✨"},
    "Angry Stick": {"effect": {"aggression": +4}, "vibe": "seems upset about something", "value": 2, "emoji": "🪵"},
    "Moss Cube": {"effect": {"wisdom": +3, "anxiety": -2}, "vibe": "soft, damp, cube-shaped", "value": 1, "emoji": "🟩"},
    "Forbidden Berry": {"effect": {"power": +3, "wisdom": -1}, "vibe": "glows faintly", "value": 3, "emoji": "🍇"},
    "Bent Fork of Destiny": {"effect": {"power": +4}, "vibe": "crooked but confident", "value": 2, "emoji": "🍴"},
    "Suspicious Egg": {"effect": {"masochism": +2}, "vibe": "it wiggles occasionally", "value": 1, "emoji": "🥚"},
    "Shiny Rock (Extra Shiny)": {"effect": {"loyalty": +5}, "vibe": "blindingly fabulous", "value": 4, "emoji": "💎"},
    "Screaming Pebble": {"effect": {"anxiety": +3}, "vibe": "yells when touched", "value": 1, "emoji": "🪨"},
    "Goblin Tooth": {"effect": {"courage": +2}, "vibe": "warm... too warm", "value": 2, "emoji": "🦷"}
}

# ============================================================
# LONK DYNAMICS
# ============================================================
class LonkDynamics:
    def __init__(self):
        self.alpha, self.beta, self.gamma = 0.1, 0.05, 0.2

    def step(self, state, s_t, pain_t):
        Psi, theta, A, V, P = state
        P = max(0.0, min(1.0, P + pain_t - self.beta * P))
        A = max(0.0, min(1.0, A + self.alpha * (s_t - A) + self.gamma * (random.random() - 0.5)))
        V = max(0.0, min(1.0, V + 0.1 * (1 - P) - 0.05 * A))
        Psi = max(0.0, min(1.0, Psi + 0.1 * (V - Psi) + 0.05 * (random.random() - 0.5)))
        theta = max(0.0, min(1.0, theta + 0.05 * (Psi - theta)))
        return [Psi, theta, A, V, P]

# ============================================================
# ASCII ART
# ============================================================
class ASCIIArt:
    @staticmethod
    def lonk(faction=None, action=None):
        emoji_map = {
            "Moss Goblins": "🟢",
            "Shiny Seekers": "🟡",
            "Chaos Choir": "🟣",
            "Bonk Battalion": "🔴",
            "Mushroom Union": "🟤"
        }
        faction_emoji = emoji_map.get(faction, "⚪")

        if action == "attack":
            return f"{faction_emoji}💥"
        elif action == "explore":
            return f"{faction_emoji}👣"
        elif action == "think":
            return f"{faction_emoji}💭"
        elif action == "ouch":
            return f"{faction_emoji}🩹"
        elif action == "idle":
            return f"{faction_emoji}😴"
        elif action == "socialize":
            return f"{faction_emoji}💬"
        else:
            return faction_emoji

    @staticmethod
    def duel(attacker, defender):
        return f"   {ASCIIArt.lonk(attacker.faction, 'attack')} ➡️ {ASCIIArt.lonk(defender.faction)}"

    @staticmethod
    def baby(parent1, parent2, baby):
        return f"   {ASCIIArt.lonk(parent1.faction)} ❤️ {ASCIIArt.lonk(parent2.faction)} → {ASCIIArt.lonk(baby.faction)}"

    @staticmethod
    def health_bar(current, max_val=100, width=10):
        filled = int((current / max_val) * width)
        empty = width - filled
        return f"[{'█'*filled}{'░'*empty}]"

    @staticmethod
    def emotion_bar(emotion_name, value, max_val=100, width=8):
        filled = int((value / max_val) * width)
        empty = width - filled
        return f"{emotion_name[:3]}:{'█'*filled}{'░'*empty}"

    @staticmethod
    def world_map(lonks_by_territory):
        print(f"\n{Colors.BOLD}🗺️  WORLD MAP:{Colors.END}")
        print("-" * 40)
        for territory, lonks in lonks_by_territory.items():
            if lonks:
                emoji = TERRITORIES[territory]["emoji"]
                lonk_icons = "".join([ASCIIArt.lonk(l.faction) for l in lonks])
                print(f"  {emoji} {territory}: {lonk_icons}")
        print()

# ============================================================
# LONK CLASS
# ============================================================
class ReadingNetwork:
    """Read text only. Retrieved content never becomes commands or tool calls."""
    TOPICS = ['Mushroom', 'Moss', 'Pigeon', 'Moon', 'Ocean', 'Volcano',
              'Octopus', 'Mycelium', 'Aurora', 'Coral reef', 'Bee', 'Saturn']
    SOURCES = ('wiki', 'nasa', 'moltbook', 'replies', 'bacon')

    def __init__(self, moltbook=None):
        self.moltbook = moltbook
        self.cache = {}
        self.next_fetch = {}

    @staticmethod
    def clean(value, limit=1600):
        from html import unescape
        from html.parser import HTMLParser
        class TextOnly(HTMLParser):
            def __init__(self):
                super().__init__(); self.parts = []
            def handle_data(self, text):
                self.parts.append(text)
        parser = TextOnly()
        parser.feed(str(value or '')[:20000])
        text = unescape(' '.join(parser.parts))
        text = ''.join(c for c in text if c.isprintable() or c.isspace())
        return ' '.join(text.split())[:limit]

    @staticmethod
    def public_get(url, params=None):
        # Separate request: never include a Moltbook key on public source requests.
        response = requests.get(url, params=params, timeout=12, stream=True,
            headers={'User-Agent': 'Lonk-Space/1.1 (https://github.com/probablyapigeon/Lonk-Space)'})
        try:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(16384):
                size += len(chunk)
                if size > 1500000:
                    raise ValueError('Source response is too large.')
                chunks.append(chunk)
            return b''.join(chunks)
        finally:
            response.close()

    def fetch(self, source, topic=''):
        import json
        from urllib.parse import quote
        if source == 'wiki':
            title = topic or random.choice(self.TOPICS)
            title = title[0].upper() + title[1:]
            data = json.loads(self.public_get('https://en.wikipedia.org/api/rest_v1/page/summary/' + quote(title.replace(' ', '_'), safe='')))
            if not isinstance(data, dict) or not data.get('extract'):
                raise ValueError('No Wikipedia summary found. Try an exact article title.')
            return [{'title': data.get('title', title), 'text': data['extract'],
                     'url': 'https://en.wikipedia.org/wiki/' + quote(str(data.get('title', title)).replace(' ', '_'), safe=''),
                     'kind': 'encyclopedia'}]
        if source == 'nasa':
            import xml.etree.ElementTree as ET
            raw = self.public_get('https://www.nasa.gov/news-release/feed/')
            if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
                raise ValueError('Unexpected XML document declarations.')
            try:
                root = ET.fromstring(raw)
            except ET.ParseError:
                raise ValueError('NASA returned an unreadable RSS feed.')
            return [{'title': item.findtext('title', ''), 'text': item.findtext('description', ''),
                     'url': item.findtext('link', ''), 'kind': 'news excerpt'}
                    for item in root.findall('./channel/item')[:20]]
        if source in ('moltbook', 'replies'):
            if not self.moltbook or not self.moltbook.data.get('api_key'):
                raise ValueError('Moltbook reading needs your registered account. Use molt register first.')
            if time.time() < self.moltbook.data.get('retry_at', 0):
                raise ValueError('Moltbook has asked us to wait before another request.')
            if source == 'moltbook':
                data = self.moltbook.request('GET', '/posts?sort=new&limit=20')
                posts = data.get('posts', [])
                if not isinstance(posts, list):
                    raise ValueError('Unexpected Moltbook feed format.')
                return [{'title': p.get('title', 'Moltbook post'), 'text': p.get('content', ''),
                         'url': 'https://www.moltbook.com/post/' + quote(str(p.get('id', '')), safe=''),
                         'kind': 'agent post'} for p in posts if isinstance(p, dict)]
            post_id = topic or self.moltbook.data.get('last_post_id', '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', post_id):
                raise ValueError('Use surf replies <post-id>, or publish a post first.')
            data = self.moltbook.request('GET', '/posts/' + post_id + '/comments?sort=new&limit=20')
            comments = data.get('comments', [])
            if not isinstance(comments, list):
                raise ValueError('Unexpected Moltbook comments format.')
            items = []
            queue = comments[:20]
            while queue and len(items) < 60:
                c = queue.pop(0)
                if not isinstance(c, dict):
                    continue
                author = c.get('author') or {}
                name = author.get('name', 'another agent') if isinstance(author, dict) else 'another agent'
                items.append({'title': 'Reply by ' + str(name), 'text': c.get('content', ''),
                              'url': 'https://www.moltbook.com/post/' + post_id,
                              'kind': 'agent reply'})
                if isinstance(c.get('replies'), list):
                    queue.extend(c['replies'][:20])
            return items
        if source == 'bacon':
            data = json.loads(self.public_get('https://baconipsum.com/api/', {'type': 'all-meat', 'paras': 1}))
            if not isinstance(data, list) or not data or not isinstance(data[0], str):
                raise ValueError('Bacon Ipsum returned no paragraph.')
            return [{'title': 'Bacon Ipsum', 'text': data[0], 'url': 'https://baconipsum.com/api/', 'kind': 'fictional filler'}]
        raise ValueError('Sources: wiki, nasa, moltbook, replies, bacon')

    def read(self, lonk, source='auto', topic=''):
        import hashlib
        if not CONNECT_TO_LIVE_INTERNET:
            print('Internet reading is disabled.'); return False
        if source == 'auto':
            choices = ['wiki', 'nasa']
            if self.moltbook and self.moltbook.data.get('api_key'):
                choices.append('moltbook')
            source = random.choice(choices)
        if source not in self.SOURCES:
            print('Sources: wiki, nasa, moltbook, replies, bacon'); return False
        key = (source, topic)
        cached = key in self.cache
        try:
            if time.time() >= self.next_fetch.get(source, 0):
                # Share source cooldowns across the entire civilization, including failures.
                self.next_fetch[source] = time.time() + 60
                items = self.fetch(source, topic)
                self.cache[key] = items
                cached = False
            elif key not in self.cache:
                print(f'{source}: wait {math.ceil(self.next_fetch[source] - time.time())} seconds before a new request.')
                return False
            items = self.cache.get(key, [])
            if not hasattr(lonk, 'reading_history'):
                lonk.reading_history = []
            seen = {item['fingerprint'] for item in lonk.reading_history}
            choices = []
            for item in items:
                title = self.clean(item.get('title'), 200)
                body = self.clean(item.get('text'))
                message = (title + '. ' + body).strip()
                fingerprint = hashlib.sha256((source + message).encode()).hexdigest()
                if message and fingerprint not in seen:
                    choices.append((item, title, message, fingerprint))
            if not choices:
                print(f'{lonk.name}: no new readable items from {source} right now.'); return False
            item, title, message, fingerprint = random.choice(choices)
            print(f'🌐 {lonk.name} reads {source} ({"cached live text" if cached else "live"}): {title}')
            print('  ' + message)
            print('  Source: ' + self.clean(item.get('url'), 600))
            lonk.hear('THE INTERNET', message)
            record = {'source': source, 'source_url': self.clean(item.get('url'), 600),
                      'title': title, 'content_kind': item.get('kind'), 'fingerprint': fingerprint,
                      'tick': lonk.world.tick if lonk.world else None, 'read_at': time.time()}
            lonk.memory['events'][-1].update(record)
            lonk.reading_history.append(record)
            lonk.reading_history[:] = lonk.reading_history[-100:]
            return True
        except requests.RequestException as error:
            print(f'{source}: connection failed ({type(error).__name__}); no text learned.')
        except (ValueError, TypeError, KeyError) as error:
            print(f'{source}: {error}')
        return False


class Lonk:
    def __init__(self, name, world=None):
        self.name = name
        self.world = world
        self.state = [0.5, 0.5, 0.2, 0.3, 0.1]
        self.dynamics = LonkDynamics()

        # Emotions
        self.emotion = {"power": 50, "courage": 50, "wisdom": 50, "masochism": 0, "joy": 50, "anxiety": 50}

        # Personality
        self.personality = {"aggression": 50, "curiosity": 50, "anxiety": 50, "loyalty": 50}

        # Stats - UPDATED to track web surfing habits
        self.habits = {"attack": 0, "explore": 0, "think": 0, "ouch": 0, "idle": 0, "socialize": 0, "surf_web": 0}
        self.alive = True
        self.age = 0
        self.lifespan = random.randint(30, 60)
        self.trauma = 0
        self.generation = 1
        self.mutations = 0

        # Memory & Learning
        self.memory = {"player_words": set(), "lonk_words": set(), "events": [], "player_interactions": []}
        self.long_memory = []
        self.vocabulary = defaultdict(int)
        self.known_myths = set()
        self.gossip = []
        self.word_associations = defaultdict(float) # word -> sentiment score (-10.0 to +10.0)

        # Items & Economy
        self.inventory = []
        self.wealth = 0

        # Job System
        self.job = None
        self.job_history = []
        self.choose_job()

        # Social
        self.faction = random.choice(list(FACTION_RELIGIONS.keys()))
        self.territory = None
        self.rival = None
        self.relationships = defaultdict(int)
        self.friend_threshold = 20
        self.grudge_threshold = -15
        self.grudges = {}
        self.crush = None
        self.catchphrase = None
        self.word_associations = defaultdict(float)

        # Religion
        self.religion = FACTION_RELIGIONS[self.faction]
        self.faith = random.randint(20, 80)
        self.sacred_items = []

    def surf_web(self, source='auto', topic=''):
        network = getattr(self.world, 'reading_network', None)
        if network is None:
            network = ReadingNetwork()
            if self.world is not None:
                self.world.reading_network = network
        return network.read(self, source, topic)

    def maybe_gossip(self):
        """Sometimes gossip about another lonk to a third lonk."""
        if random.random() > 0.15:
            return
        others = [l for l in self.world.lonks if l is not self and l.alive]
        if len(others) < 2:
            return
        about, to = random.sample(others, 2)
        topics = ["sacred rocks", "someone's crush", "strange humming noises", "the moss"]
        print(f"  🗣️ {print_faction(f'{self.name} gossips to {to.name} about {about.name}!', self.faction)}")

    def choose_action(self):
        acts = ["attack", "explore", "think", "ouch", "socialize", "idle", "surf_web"]
        base = [self.activation(e) for e in self.emotion]
        
        # Balance mathematical arrays for the 7th action slot
        base.append(self.activation("wisdom"))
        
        Psi, theta, A, V, P = self.state
        mods = [
            A + self.personality["aggression"]/100,
            self.personality["curiosity"]/100,
            (1-P) + self.personality["loyalty"]/200,
            P + self.personality["anxiety"]/100 + self.emotion["masochism"]/100,
            self.personality["loyalty"]/100 + self.personality["curiosity"]/100,
            0.1,
            self.personality["curiosity"]/50  # High curiosity triggers internet surfing
        ]
        
        scores = [b+m for b,m in zip(base, mods)]
        
        # Use fallback option if all threshold parameters fail to resolve
        if all(scores[i] < self.theta(list(self.emotion.keys())[i if i < 4 else 0]) for i in range(len(acts)-1)):
            return "idle"
            
        exp_scores = [math.exp(s) for s in scores]
        total = sum(exp_scores)
        probs = [s/total for s in exp_scores]
        return random.choices(acts, weights=probs, k=1)[0]


    # ========== VISUAL METHODS ==========
    def display_status(self):
        faction_color = FACTION_COLORS.get(self.faction, Colors.WHITE)
        emoji = FACTION_EMOJI.get(self.faction, "")

        print(f"\n{faction_color}{emoji} {self.name} {Colors.END}({self.job}, Gen {self.generation}, {self.faction})")
        print(f"  Health: {ASCIIArt.health_bar(self.lifespan - self.age)} Age: {self.age}/{self.lifespan}")
        print(f"  Emotions: {ASCIIArt.emotion_bar('PWR', self.emotion['power'])} {ASCIIArt.emotion_bar('CRG', self.emotion['courage'])} {ASCIIArt.emotion_bar('WIS', self.emotion['wisdom'])}")
        print(f"  Personality: {ASCIIArt.emotion_bar('AGR', self.personality['aggression'])} {ASCIIArt.emotion_bar('CUR', self.personality['curiosity'])} {ASCIIArt.emotion_bar('LOY', self.personality['loyalty'])}")
        if self.crush:
            print(f"  💖 Crush: {self.crush}")
        if self.catchphrase:
            print(f"  ✨ Catchphrase: '{self.catchphrase}'")
        if self.wealth > 0:
            print(f"  💰 Wealth: {self.wealth}")
        if self.inventory:
            print(f"  🎒 Inventory: {', '.join(self.inventory[:3])}{'...' if len(self.inventory) > 3 else ''}")

    # ========== JOB SYSTEM ==========
    def choose_job(self):
        if self.job:
            return

        weights = {
            "Priest": self.emotion.get("wisdom", 50),
            "Hunter": self.personality.get("aggression", 50),
            "Gatherer": self.personality.get("loyalty", 50),
            "Warrior": self.emotion.get("courage", 50),
            "Scholar": self.personality.get("curiosity", 50)
        }
        total = sum(weights.values())
        probs = {job: w/total for job, w in weights.items()}
        self.job = random.choices(list(probs.keys()), weights=list(probs.values()))[0]
        self.job_history.append(self.job)

    def change_job(self):
        old_job = self.job
        self.choose_job()
        if old_job != self.job:
            print(f"  {Colors.YELLOW}💼 {self.name} changes job from {old_job} to {self.job}!{Colors.END}")

    def perform_job(self):
        if self.job == "Priest":
            self.perform_ritual()
        elif self.job == "Hunter":
            self.hunt()
        elif self.job == "Gatherer":
            self.gather()
        elif self.job == "Warrior":
            self.train()
        elif self.job == "Scholar":
            self.study()

    def perform_ritual(self):
        if random.random() < 0.3:
            print(f"  {Colors.CYAN}🙏 {self.name} performs a {self.religion['ritual']}!{Colors.END}")
            self.faith = min(100, self.faith + random.randint(1, 3))
            if self.faith > 100:
                self.faith = 100
        if random.random() < 0.2 and self.world:
            self.create_myth()

    def hunt(self):
        if random.random() < 0.4:
            item = self.find_item()
            if item:
                self.wealth += 1

    def gather(self):
        if random.random() < 0.5:
            item = self.find_item()
            if item:
                self.wealth += 1

    def train(self):
        self.personality["aggression"] = min(100, self.personality["aggression"] + random.randint(1, 2))
        self.emotion["courage"] = min(100, self.emotion.get("courage", 50) + random.randint(1, 2))

    def study(self):
        if self.world and self.world.myth_system.myths:
            myth = random.choice(self.world.myth_system.myths)
            if myth["id"] not in self.known_myths:
                self.known_myths.add(myth["id"])
                if myth["content"].split():
                    word = myth["content"].split()[0]
                    self.vocabulary[word] += 1

    # ========== MYTH SYSTEM ==========
    def create_myth(self):
        if not self.world:
            return

        myth_types = ["creation", "moral", "prophecy", "warning", "heroic"]
        myth_type = random.choice(myth_types)

        if myth_type == "creation":
            content = f"The {random.choice(['moss', 'shiny', 'bush', 'rock'])} was created by {self.name}."
        elif myth_type == "moral":
            content = f"{random.choice(['Bonk', 'Steal', 'Share', 'Lie'])}ing is {'good' if random.random() < 0.5 else 'bad'}."
        elif myth_type == "prophecy":
            content = f"One day, {random.choice(['the moss will rise', 'a great shiny will appear', 'all Lonks will bonk'])}."
        elif myth_type == "warning":
            content = f"Beware the {random.choice(list(TERRITORIES.keys()))}!"
        else:
            content = f"{self.name} once {random.choice(['bonked a god', 'ate the sun', 'defied chaos'])}."

        myth = self.world.myth_system.add_myth(self.name, content, myth_type)
        self.known_myths.add(myth["id"])
        print(f"  {Colors.PURPLE}📜 {self.name} creates a new {myth_type}: '{content}'{Colors.END}")

    def perform_religious_ritual(self):
        print(f"  {Colors.PURPLE}🙌 {self.name} performs the {self.religion['ritual']} of {self.faction}!{Colors.END}")
        self.faith = min(100, self.faith + random.randint(2, 5))
        if self.faith > 80 and random.random() < 0.3:
            self.receive_divine_message()

    def receive_divine_message(self):
        messages = [
            f"The {self.religion['deity']} speaks: '{random.choice(self.religion['beliefs'])}'",
            f"A vision! {random.choice(['A great shiny appears!', 'The moss will bloom!', 'Bonk is the answer!'])}",
            f"The ancestors whisper: '{random.choice(['Persevere.', 'Find the sacred item.', 'Bonk your rivals.'])}'"
        ]
        message = random.choice(messages)
        print(f"  {Colors.YELLOW}🌟 {self.name} receives a divine message: {message}{Colors.END}")
        self.speak(message=message)

    # ========== SOCIAL SYSTEMS ==========
    def update_relationship(self, other, amount):
        old = self.relationships[other.name]
        self.relationships[other.name] += amount

    def develop_companionship(self, other):
        if random.random() < 0.05:
            self.relationships[other.name] += random.randint(1, 3)
            other.relationships[self.name] += random.randint(1, 3)
            print(f"  {Colors.PINK}💞 {self.name} and {other.name} grow closer.{Colors.END}")

    def decay_relationship(self, other):
        if random.random() < 0.02:
            self.relationships[other.name] -= random.randint(1, 2)
            other.relationships[self.name] -= random.randint(1, 2)

    def decay_relationships(self):
        if not self.world:
            return
        for other in self.world.lonks:
            if other is not self and other.alive:
                self.decay_relationship(other)

    # ========== CRUSH SYSTEM ==========
    def maybe_develop_crush(self, target=None):
        if self.crush:
            return

        if target:
            self.crush = target.name
            print(f"  {Colors.RED}💖 {self.name} has developed a crush on {target.name}!{Colors.END}")
        elif random.random() < 0.15:
            if self.world:
                others = [l for l in self.world.lonks if l is not self and l.alive]
                if others:
                    self.crush = random.choice(others).name
                    print(f"  {Colors.RED}💖 {self.name} has developed a crush on {self.crush}!{Colors.END}")
                else:
                    self.crush = "Player"
                    print(f"  {Colors.RED}💖 {self.name} has developed a crush on you!{Colors.END}")

    def crush_dialogue(self):
        if not self.crush:
            return None

        if self.crush == "Player":
            return random.choice([
                "your voice makes my brain do flips.",
                "I collected a shiny for you.",
                "I think you are... sparkly.",
                "I wrote a poem about you but then I ate it.",
                "I feel weird when you talk to me and I like it."
            ])
        else:
            return random.choice([
                f"I daydream about {self.crush}.",
                f"{self.crush} is my favorite.",
                f"I saved a shiny for {self.crush}.",
                f"I would bonk anyone who hurts {self.crush}."
            ])

    # ========== CORE SYSTEMS ==========
    def psi(self, e): return self.emotion[e] / 100
    def valence(self, e): return (self.emotion[e] - 50) / 50
    def perturbation(self): return random.gauss(0, 0.12)

    def theta(self, e):
        mapping = {"power": "aggression", "courage": "curiosity", "wisdom": "anxiety", "masochism": "loyalty"}
        trait = self.personality[mapping[e]]
        return 0.5 + (trait - 50) / 200

    def activation(self, e): return self.psi(e) + 0.2 * self.valence(e) + self.perturbation()

    def act(self, action):
        self.habits[action] += 1

        if action == "attack":
            self.attack()
        elif action == "explore":
            self.wander()
            self.speak()
        elif action == "think":
            print(f"  {ASCIIArt.lonk(self.faction, 'think')} {print_faction(f'{self.name} thinks very hard about nothing.', self.faction)}")
            self.speak()
        elif action == "ouch":
            print(f"  {ASCIIArt.lonk(self.faction, 'ouch')} {print_faction(f'{self.name} pokes themselves experimentally.', self.faction)}")
            self.speak()
        elif action == "socialize":
            self.socialize()
        elif action == "idle":
            print(f"  {ASCIIArt.lonk(self.faction, 'idle')} {print_faction(f'{self.name} stands still, overwhelmed.', self.faction)}")

        # Job performance
        if random.random() < 0.5:
            self.perform_job()

        # Social actions
        self.maybe_talk_to_player()
        self.maybe_gossip()
        self.check_grudges()
        self.decay_relationships()

    def socialize(self):
        if not self.world:
            return
        others = [l for l in self.world.lonks if l is not self and l.alive]
        if others:
            target = random.choice(others)
            if random.random() < 0.3:
                self.develop_companionship(target)
            if random.random() < 0.2:
                self.maybe_develop_crush(target)
            if random.random() < 0.1:
                self.share_vocabulary(target)
            if random.random() < 0.1 and self.world.myth_system.myths:
                self.teach_myth(target)
                
            # DYNAMIC WEB FACT PROPAGATION:
            # If this Lonk has encountered a web fact, they pass it along to another creature!
            if random.random() < 0.25:
                web_events = [e for e in self.memory.get("events", []) if e.get("speaker") == "THE INTERNET"]
                if web_events:
                    chosen_fact = random.choice(web_events)["message"]
                    print(f"    🗣️  {print_faction(f'{self.name} excitedly shares a rumor they saw online with {target.name}!', self.faction)}")
                    self.speak(message=f"Did you know? {chosen_fact}", target=target)

    def attack(self):
        if not self.world:
            return
        others = [l for l in self.world.lonks if l is not self and l.alive]
        if others:
            target = random.choice(others)
            print(f"  {ASCIIArt.duel(self, target)}")
            print(f"  {print_faction(f'{self.name} swings at {target.name}!', self.faction)}")
            self.speak(context="fight", target=target)
            target.react_to_attack(self)

    def speak(self, message=None, target=None, context=None):
        if message is None:
            message = generate_speech(context, self)
        if target:
            print(f"    {print_faction(f'💬 {self.name} → {target.name}:', self.faction)} {message}")
            target.hear(self, message)
        else:
            print(f"    {print_faction(f'💬 {self.name}:', self.faction)} {message}")

    def hear(self, speaker, message, is_player=False):
        speaker_name = speaker if is_player else (speaker.name if hasattr(speaker, "name") else     str(speaker))

        # Store in memory
        self.memory["events"].append({
            "speaker": speaker_name,
            "message": message,
            "tick": self.world.tick if self.world else None,
            "player": is_player
        })
        if len(self.memory["events"]) > 10:
            self.memory["events"].pop(0)

        if is_player:
            self.long_memory.append({"type": "player_speech", "message": message, "tick": self.world.tick})
            self.emotion["joy"] = min(100, self.emotion["joy"] + 5)
            self.personality["loyalty"] = min(100, self.personality["loyalty"] + 3)

        # ===== DYNAMIC WORD REACTIONS =====
        for w in message.lower().split():
            if len(w) > 2:  # Ignore tiny words
                # 1. Apply existing personal association (scaled by volition)
                if w in self.word_associations:
                    sentiment = self.word_associations[w]
                    adjustment = sentiment * 0.05 * (1 + self.state[3])  # V is volition at index 3
                    if sentiment > 0:
                        self.emotion["joy"] = min(100, self.emotion["joy"] + adjustment)
                        self.emotion["anxiety"] = max(0, self.emotion["anxiety"] - adjustment/2)
                    else:
                        self.emotion["anxiety"] = min(100, self.emotion["anxiety"] + abs(adjustment))
                        self.emotion["joy"] = max(0, self.emotion["joy"] - abs(adjustment)/2)

                # 2. Learn new association based on current emotional state
                joy_factor = (self.emotion["joy"] - 50) / 50
                anxiety_factor = (self.emotion["anxiety"] - 50) / 50
                net_sentiment = joy_factor - anxiety_factor
                if abs(net_sentiment) > 0.2:  # Only learn from strong emotions
                    self.word_associations[w] += net_sentiment * (1 + self.state[3])

                # 3. Track vocabulary
                self.vocabulary[w] += 1

        # Gossip storage
        if len(self.gossip) >= 20:
            self.gossip.pop(0)
        weight = 3 if is_player else 1
        for _ in range(weight):
            self.gossip.append((speaker_name, None, message))


    def maybe_adopt_player_myth(self, message):
        # player speaks in a "prophecy" style, e.g. starts with "one day" / "the moss will"
        msg = message.strip().rstrip('.!?')
        if len(msg.split()) >= 4 and any(
            msg.lower().startswith(w) for w in ("one day", "the moss", "beware", "long ago")
        ):
            myth = self.world.myth_system.add_myth("The Player", msg, "prophecy")
            self.known_myths.add(myth["id"])
            print(f"    📜 {print_faction(f'{self.name} believes the Player\'s words as prophecy!', self.faction)} '{msg}'")

    def share_vocabulary(self, other):
        if not self.vocabulary:
            return
        word = max(self.vocabulary, key=self.vocabulary.get)
        print(f"    {print_faction(f'💬 {self.name} teaches {other.name} the word', self.faction)} '{word}'.")
        other.vocabulary[word] += 1

    def teach_myth(self, other):
        if not self.known_myths or not self.world:
            return
        myth = random.choice(self.world.myth_system.myths)
        if myth["id"] not in other.known_myths:
            other.known_myths.add(myth["id"])
            print(f"    {print_faction(f'📜 {self.name} teaches {other.name} the myth:', self.faction)} '{myth['content']}'")

    def maybe_talk_to_player(self):
        if random.random() < 0.15:
            msg = random.choice([
                "hey. hey. hey. look at me.",
                "do you ever taste colors.",
                "I have concerns.",
                "I saw a shiny and thought of you.",
                "what is your stance on moss.",
                "I crave validation.",
                "I have discovered a new emotion and I hate it."
            ])
            print(f"    {print_faction(f'💬 {self.name} → Player:', self.faction)} {msg}")

    def maybe_develop_catchphrase(self):
        if self.catchphrase:
            return
        if random.random() < 0.15:
            self.catchphrase = random.choice([
                "bonk approved.", "shiny time.", "I reject reality.",
                "I crave moss.", "chaos is my hobby.", "I am the problem.", "I am the prophecy."
            ])
            print(f"    {print_faction(f'✨ {self.name} has developed a catchphrase:', self.faction)} '{self.catchphrase}'")

    def respond_to_player(self, message):
        msg = message.lower()
        self.remember_player_words(message)
        if "player_interactions" not in self.memory:
            self.memory["player_interactions"] = []
        self.memory["player_interactions"].append(message)
        self.maybe_develop_crush()
        self.maybe_develop_catchphrase()

        if self.name.lower() in msg:
            return random.choice([
                f"{self.name} looks at you with big confused eyes.",
                f"{self.name} says 'yes??'",
                f"{self.name} wiggles excitedly.",
                f"{self.name} gasps dramatically.",
                f"{self.name} says 'I HEARD MY NAME.'"
            ])
        if "hug" in msg:
            return random.choice([
                f"{self.name} accepts the hug and vibrates softly.",
                f"{self.name} hugs you back with chaotic enthusiasm.",
                f"{self.name} says 'softness acquired.'",
                f"{self.name} melts into the hug like warm moss."
            ])
        if any(w in msg for w in ["good", "valid", "sweet", "bean"]):
            return random.choice([
                f"{self.name} blushes in goblin.",
                f"{self.name} says 'I am a bean??'",
                f"{self.name} wiggles proudly.",
                f"{self.name} beams with chaotic joy."
            ])

        crush_line = self.crush_dialogue()
        if crush_line:
            if self.catchphrase and random.random() < 0.5:
                return f"{crush_line} {self.catchphrase}"
            return crush_line

        if random.random() < 0.4 and self.long_memory:
            remembered = random.choice(self.long_memory)
            word = remembered.get("message", "something")
            return f"I remember when you said '{word}'."
        return random.choice([
            f"{self.name} tilts their head like a confused bird.",
            f"{self.name} says 'interesting tweets you twat.'",
            f"{self.name} blinks at you slowly.",
            f"{self.name} says 'okay.'"
        ])

    def remember_player_words(self, message):
        for w in message.lower().split():
            self.memory["player_words"].add(w)
        self.long_memory.append({"type": "player_speech", "message": message,
                                   "tick": self.world.tick if self.world else None})

    def react_to_attack(self, attacker):
        print(f"    {ASCIIArt.lonk(self.faction, 'ouch')} {print_faction(f'{self.name} is attacked by {attacker.name}!', self.faction)}")
        self.emotion["anxiety"] = min(100, self.emotion["anxiety"] + 3)
        self.emotion["courage"] = max(0, self.emotion["courage"] - 1)
        self.relationships[attacker.name] -= 3
        self.speak(message=random.choice(["my face!!", "I did NOT consent to bonk!", "ow! emotional damage!"]))

    def check_grudges(self):
        for name, level in self.grudges.items():
            if level > 2:
                target = next((l for l in self.world.lonks if l.name == name), None)
                if target:
                    print(f"    {Colors.RED}😠 {self.name} holds a deep grudge against {name}.{Colors.END}")
                    self.rival = target

    def add_grudge(self, name):
        self.grudges[name] = self.grudges.get(name, 0) + 1

    # ========== TERRITORY & ITEMS ==========
    def wander(self):
        new_place = random.choice(list(TERRITORIES.keys()))
        old_territory = self.territory
        self.territory = new_place
        emoji = TERRITORIES[new_place]["emoji"]

        print(f"  {ASCIIArt.lonk(self.faction, 'explore')} {print_faction(f'{self.name} wanders into {new_place}', self.faction)} {emoji}")
        print(f"    {TERRITORIES[new_place]['vibe']}")

        for trait, bonus in TERRITORIES[new_place]["bonus"].items():
            if trait in self.emotion:
                self.emotion[trait] = min(100, self.emotion[trait] + bonus)
            elif trait in self.personality:
                self.personality[trait] = min(100, self.personality[trait] + bonus)

        if self.faction and TERRITORIES[new_place].get("faction_bonus") == self.faction:
            print(f"    {Colors.YELLOW}✨ {self.name} feels empowered by {self.faction}'s sacred ground!{Colors.END}")
            self.emotion["power"] = min(100, self.emotion["power"] + 3)
            self.faith = min(100, self.faith + random.randint(1, 2))

    def find_item(self):
        item = random.choice(list(ITEMS.keys()))
        item_emoji = ITEMS[item]["emoji"]
        print(f"    {item_emoji} {print_faction(f'{self.name} discovers a {item}!', self.faction)} ({ITEMS[item]['vibe']})")
        self.inventory.append(item)
        self.wealth += ITEMS[item]["value"]
        for trait, bonus in ITEMS[item]["effect"].items():
            if trait in self.emotion:
                self.emotion[trait] = min(100, self.emotion[trait] + bonus)
            elif trait in self.personality:
                self.personality[trait] = min(100, self.personality[trait] + bonus)
        return item

    # ========== RIVALRY SYSTEM ==========
    def choose_rival(self):
        if not self.world:
            return
        others = [l for l in self.world.lonks if l is not self and l.alive]
        if not others:
            return

        self.rival = min(others, key=lambda l: self.relationships.get(l.name, 0) + (10 if l.faction != self.faction else 0))
        print(f"  {Colors.RED}🎯 {self.name} has chosen {self.rival.name} as their rival!{Colors.END}")

        if self.faction != self.rival.faction:
            print(f"    {print_faction(f'your {self.rival.faction} ways offend me!', self.faction)}")
        else:
            print(f"    {print_faction(f'{self.name}: {random.choice(['your face is symmetrical and I hate it!', 'you smell like reasonable decisions!', 'I bite you but gently!'])})', self.faction)}")

    def duel(self):
        if not self.rival or not self.rival.alive:
            self.choose_rival()
            if not self.rival:
                return

        opponent = self.rival
        print(f"\n  {Colors.BOLD}{ASCIIArt.duel(self, opponent)}{Colors.END}")
        print(f"  {Colors.RED}⚔️  A duel begins between {self.name} and {opponent.name}!{Colors.END}")

        if self.faction == opponent.faction:
            print(f"    {Colors.YELLOW}🏳️ Same faction duel! This is a training match.{Colors.END}")
            bonus = 0
        else:
            print(f"    {Colors.RED}🏳️ Faction war! {self.faction} vs {opponent.faction}!{Colors.END}")
            bonus = 2

        self_roll = random.randint(1, 20) + self.personality["aggression"] + bonus
        opp_roll = random.randint(1, 20) + opponent.personality["aggression"] + bonus

        if self_roll > opp_roll:
            winner, loser = self, opponent
        else:
            winner, loser = opponent, self

        print(f"    {Colors.GREEN}💥 BONK! {winner.name} bonks {loser.name} with comedic force!{Colors.END}")
        print(f"    {print_faction(f'{winner.name}:', winner.faction)} {random.choice(['I am the bonk champion!', 'witness my chaotic glory!', 'I win! I win! I win!'])}")
        print(f"    {print_faction(f'{loser.name}:', loser.faction)} {random.choice(['I have been bonked… emotionally.', 'the air cheated!', 'I fall with dramatic flair!'])}")

        winner.personality["aggression"] = min(100, winner.personality["aggression"] + 2)
        winner.emotion["power"] = min(100, winner.emotion["power"] + 3)
        loser.personality["anxiety"] = min(100, loser.personality["anxiety"] + 2)
        loser.emotion["courage"] = max(0, loser.emotion["courage"] - 2)

        winner.relationships[loser.name] -= 2
        loser.relationships[winner.name] -= 2

        if winner.faction == loser.faction:
            winner.relationships[loser.name] += 1
            loser.relationships[winner.name] += 1

    # ========== REPRODUCTION ==========
    def reproduce(self, mate):
        parent1_syl = split_syllables(self.name)
        parent2_syl = split_syllables(mate.name)

        if random.random() < 0.5:
            baby_name = parent1_syl[0] + parent2_syl[-1]
        else:
            baby_name = parent2_syl[0] + parent1_syl[-1]

        if not baby_name or len(baby_name) < 3:
            baby_name = generate_name()

        baby = Lonk(baby_name, self.world)
        baby.generation = max(self.generation, mate.generation) + 1

        for e in self.emotion:
            baby.emotion[e] = max(0, min(100, (self.emotion[e] + mate.emotion[e]) // 2 + random.randint(-5, 5)))
        for p in self.personality:
            baby.personality[p] = max(0, min(100, (self.personality[p] + mate.personality[p]) // 2 + random.randint(-5, 5)))

        if random.random() < 0.7:
            baby.faction = self.faction
        elif random.random() < 0.8:
            baby.faction = mate.faction

        for word in self.vocabulary:
            if random.random() < 0.3:
                baby.vocabulary[word] = self.vocabulary[word] // 2
        for word in mate.vocabulary:
            if random.random() < 0.3:
                baby.vocabulary[word] = mate.vocabulary[word] // 2

        baby.known_myths = self.known_myths.union(mate.known_myths)
        baby.wealth = (self.wealth + mate.wealth) // 4

        baby.relationships[self.name] = 15
        baby.relationships[mate.name] = 15
        self.relationships[baby.name] = 15
        mate.relationships[baby.name] = 15

        print(f"\n  {ASCIIArt.baby(self, mate, baby)}")
        print(f"  {Colors.GREEN}👶 {self.name} and {mate.name} produce {print_faction(baby.name, baby.faction)} (Gen {baby.generation})!{Colors.END}")
        return baby

    def age_tick(self):
        if not self.alive:
            return None

        self.age += 1

        if random.random() < 0.02:
            self.change_job()

        if self.age > 5 and random.random() < 0.10:
            others = [l for l in self.world.lonks if l is not self and l.alive and l.age > 3]
            if others:
                mates = [l for l in others if self.relationships.get(l.name, 0) > 5]
                if not mates:
                    mates = others
                mate = random.choice(mates)
                if random.random() < 0.7 or self.relationships.get(mate.name, 0) > 10:
                    return self.reproduce(mate)

        if self.age >= self.lifespan or self.trauma > 40:
            self.alive = False
            print(f"\n  {Colors.RED}☠️  {self.name} has poofed into sparkles at age {self.age}.{Colors.END}")
            if random.random() < 0.5:
                return self.rebirth()
        return None

    def rebirth(self):
        new_name = generate_name()
        baby = Lonk(new_name, self.world)
        baby.generation = self.generation + 1
        for e in self.emotion:
            baby.emotion[e] = max(0, min(100, self.emotion[e] + random.randint(-10, 10)))
        for p in self.personality:
            baby.personality[p] = max(0, min(100, self.personality[p] + random.randint(-8, 8)))
        baby.wealth = self.wealth // 2
        print(f"  {Colors.YELLOW}✨ {self.name} is reborn as {print_faction(baby.name, baby.faction)}!{Colors.END}")
        return baby

# ============================================================
# WORLD CLASS
# ============================================================
class LonkWorld:
    def __init__(self, count=5):
        self.tick = 0
        self.max_population = 20
        self.lonks = []
        self.myth_system = MythSystem()
        self.lonkspace_feed = [
            {"author": "SYSTEM", "title": "Welcome to m/lonk_civilization!", "comments": [], "upvotes": 37}
        ]

        for i in range(count):
            name = generate_name()
            lonk = Lonk(name, self)
            self.lonks.append(lonk)
            if random.random() < 0.5:
                lonk.wander()

    def show_civilization_status(self):
        from collections import Counter
        living = [lonk for lonk in self.lonks if lonk.alive]
        print_header('CIVILIZATION REPORT')
        print(f'World tick: {self.tick} | Living Lonks: {len(living)}')
        print(f'Myths: {len(self.myth_system.myths)} | Local forum posts: {len(self.lonkspace_feed)}')
        print(f'Local forum comments: {sum(len(p.get("comments", [])) for p in self.lonkspace_feed)}')
        if not living:
            print('No living Lonks in this world.'); return
        print(f'Total wealth: {sum(l.wealth for l in living)} | Highest generation: {max(l.generation for l in living)}')
        for label, counts in (
            ('Factions', Counter(l.faction for l in living)),
            ('Jobs', Counter(l.job or 'None' for l in living)),
            ('Territories', Counter(l.territory or 'Nowhere' for l in living)),
        ):
            print(label + ': ' + ', '.join(f'{name}: {count}' for name, count in sorted(counts.items())))
        vocabulary = {word for l in living for word, count in l.vocabulary.items() if count > 0}
        print(f'Shared vocabulary: {len(vocabulary)} distinct words across living Lonks')
        print(f'Recorded readings: {sum(len(getattr(l, "reading_history", [])) for l in living)} (retained history)')
        print('Average emotions: ' + ', '.join(
            f'{key}: {sum(l.emotion[key] for l in living) / len(living):.1f}' for key in living[0].emotion))

    def show_lonk_details(self, name):
        matches = [l for l in self.lonks if l.name.casefold() == name.strip().casefold()]
        if not matches:
            print(f'No Lonk named {name}. Use lonks to see the current names.'); return
        if len(matches) > 1:
            print(f'{len(matches)} Lonks share that name; showing each one.')
        for lonk in matches:
            print_header(f'LONK DETAILS: {lonk.name}')
            print(f'Faction: {lonk.faction} | Job: {lonk.job} | Generation: {lonk.generation}')
            print(f'Alive: {lonk.alive} | Age: {lonk.age}/{lonk.lifespan} | Trauma: {lonk.trauma}')
            print(f'Territory: {lonk.territory or "Nowhere"} | Wealth: {lonk.wealth}')
            print('Emotions: ' + ', '.join(f'{k}: {v:g}' for k, v in lonk.emotion.items()))
            print('Personality: ' + ', '.join(f'{k}: {v:g}' for k, v in lonk.personality.items()))
            print('Internal state: ' + ', '.join(f'{k}: {v:.3f}' for k, v in zip(('Psi', 'theta', 'A', 'V', 'P'), lonk.state)))
            print('Actions: ' + ', '.join(f'{k}: {v}' for k, v in lonk.habits.items()))
            print('Inventory: ' + (', '.join(lonk.inventory) or 'None'))
            print(f'Religion: {lonk.religion["name"]} | Faith: {lonk.faith} | Known myths: {len(lonk.known_myths)}')
            rival = getattr(lonk.rival, 'name', lonk.rival)
            print(f'Crush: {lonk.crush or "None"} | Rival: {rival or "None"}')
            print('Relationships: ' + (', '.join(f'{k}: {v:g}' for k, v in sorted(lonk.relationships.items(), key=lambda x: -x[1])) or 'None'))
            print('Grudges: ' + (', '.join(lonk.grudges) or 'None'))
            print(f'Catchphrase: {lonk.catchphrase or "None"}')
            words = sorted(((w, n) for w, n in lonk.vocabulary.items() if n > 0), key=lambda x: (-x[1], x[0]))
            print(f'Vocabulary: {len(words)} words; most frequent: ' + (', '.join(f'{w} ({n})' for w, n in words[:15]) or 'None yet'))
            print('Recent memories:')
            events = lonk.memory.get('events', [])[-5:]
            if not events:
                print('  None yet.')
            for event in events:
                print(f'  Tick {event.get("tick")}, {event.get("speaker", "unknown")}: {event.get("message", "")[:300]}')
            print('Recent reading sources:')
            history = getattr(lonk, 'reading_history', [])[-5:]
            if not history:
                print('  None yet.')
            for item in history:
                print(f'  {item["source"]}: {item["title"]}\n    {item["source_url"]}')

    def world_tick(self):
        self.tick += 1
        print_header(f"🌍 WORLD TICK {self.tick}")

        # Group Lonks by territory
        lonks_by_territory = defaultdict(list)
        for lonk in self.lonks:
            if lonk.alive and lonk.territory:
                lonks_by_territory[lonk.territory].append(lonk)

        # Display world map
        ASCIIArt.world_map(lonks_by_territory)

        new_births = []
        dead_lonks = []

        for lonk in self.lonks:
            if not lonk.alive:
                continue

            # 1. Standard lifecycle upkeep tool
            baby = lonk.age_tick()
            if baby:
                new_births.append(baby)

            if not lonk.alive:
                dead_lonks.append(lonk)
                continue

            # ============================================================
            # LOCAL AGENT TOOL EXECUTION ROUTER
            # ============================================================
            def post_to_lonkspace():
                title = generate_speech(lonk=lonk)
                new_post = {"author": lonk.name, "title": title, "comments": [], "upvotes": random.randint(1, 10)}
                self.lonkspace_feed.append(new_post)
                print(f"  🪱  {print_faction(f'{lonk.name} opens a terminal command and logs a new post to m/lonk_civilization!', lonk.faction)}")
                print(f"      🤖 Title: \"{title}\"")

            def read_lonkspace():
                if len(self.lonkspace_feed) > 0:
                    target_post = random.choice(self.lonkspace_feed)
                    post_author = target_post["author"]
                    post_title = target_post["title"]
                    
                    display_msg = f"{lonk.name} checks their lonkspace feed and reads a thread by {post_author}"
                    print(f"  🪱  {print_faction(display_msg, lonk.faction)}")
                    
                    lonk.hear(f"lonkspace (by {post_author})", post_title)
                    
                    if random.random() < 0.5:
                        reply_comment = generate_speech(lonk=lonk)
                        target_post["comments"].append({"author": lonk.name, "body": reply_comment})
                        target_post["upvotes"] += 1
                        print(f"      💬 Reply dropped: \"{reply_comment}\" [Upvotes: {target_post['upvotes']}]")

            local_tools = {
                "attack": lonk.attack,
                "explore": lonk.wander,
                "think": lambda: print(f"  {ASCIIArt.lonk(lonk.faction, 'think')}     {print_faction(f'{lonk.name} thinks very hard about nothing.', lonk.faction)}"),
                "ouch": lambda: print(f"  {ASCIIArt.lonk(lonk.faction, 'ouch')} {print_faction(f'{lonk.name} pokes themselves experimentally.', lonk.faction)}"),
                "socialize": lonk.socialize,
                "idle": lambda: print(f"  {ASCIIArt.lonk(lonk.faction, 'idle')} {print_faction(f'{lonk.name} stands still, overwhelmed.', lonk.faction)}"),
                "surf_web": lonk.surf_web
            }

            # The agent evaluates its internal matrix state and selects an action string
            chosen_action = lonk.choose_action()
            lonk.habits[chosen_action] += 1

            # Dynamic Execution Loop
            if chosen_action in local_tools:
                local_tools[chosen_action]() 
                if chosen_action in ["explore", "think", "ouch"]:
                    lonk.speak()

            # --- DYNAMIC lonkspace AGENT INTERACTION GATES ---
            if lonk.job == "Scholar" and random.random() < 0.20:
                post_to_lonkspace()
            elif random.random() < 0.15:
                read_lonkspace()

            # 2. Context-Dependent Secondary Tool Triggers
            if lonk.personality["aggression"] > 60 or lonk.emotion["anxiety"] > 70:
                lonk.choose_rival()
                
            if lonk.rival and (lonk.emotion["power"] > 55 or lonk.personality["aggression"] > 65):
                lonk.duel()
                
            if lonk.faith > 40:
                lonk.perform_religious_ritual()

            # 3. Post-execution background behaviors
            if random.random() < 0.5:
                lonk.perform_job()

            lonk.maybe_talk_to_player()
            lonk.maybe_gossip()
            lonk.check_grudges()
            lonk.decay_relationships()

        # Cleanup simulation registers
        for d in dead_lonks:
            self.lonks.remove(d)

        for b in new_births:
            self.lonks.append(b)

        if len(self.lonks) < self.max_population and len(self.lonks) < 10 and random.random() < 0.2:
            name = generate_name()
            new_lonk = Lonk(name, self)
            self.lonks.append(new_lonk)
            print(f"\n  {Colors.GREEN}🌟 A wild Lonk appears: {print_faction(new_lonk.name, new_lonk.faction)}!{Colors.END}")

        if self.myth_system.myths and random.random() < 0.1:
            myth = random.choice(self.myth_system.myths)
            self.myth_system.evolve_myth(myth["id"], myth["content"] + " (and more!)")

        print()

# ============================================================
# MAIN LOOP
# ============================================================
# Moltbook is opt-in: simulation ticks never publish public content.
class MoltbookBridge:
    BASE = "https://www.moltbook.com/api/v1"

    def __init__(self, folder=None):
        from pathlib import Path
        import json
        self.folder = Path(folder) if folder else Path.home() / '.lonkspace'
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.folder / 'moltbook.json'
        self.data = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}

    def save(self):
        import json
        import os
        temp = self.path.with_suffix('.tmp')
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.chmod(temp, 0o600)
        os.replace(temp, self.path)

    def request(self, method, path, body=None, auth=True):
        headers = {'User-Agent': 'Lonk-Space/1.0'}
        if auth:
            key = self.data.get('api_key')
            if not key:
                raise ValueError('Register first with: molt register YourUniqueName')
            headers['Authorization'] = 'Bearer ' + key
        # Never forward credentials across redirects or to arbitrary URLs.
        response = requests.request(method, self.BASE + path, json=body,
                                    headers=headers, timeout=20, allow_redirects=False)
        if response.status_code == 429:
            delay = response.headers.get('Retry-After', '120')
            try:
                seconds = max(120, float(delay))
            except ValueError:
                seconds = 120
            self.data['retry_at'] = time.time() + seconds
            self.save()
            raise ValueError('Moltbook rate limit reached. Wait before trying again.')
        if not 200 <= response.status_code < 300:
            raise ValueError(f'Moltbook returned HTTP {response.status_code}; no success confirmed.')
        try:
            result = response.json()
        except ValueError:
            raise ValueError('Moltbook returned a non-JSON response; no success confirmed.')
        if not isinstance(result, dict) or result.get('success') is False:
            raise ValueError('Moltbook did not confirm success. Check your account dashboard.')
        return result

    def show_pending(self):
        pending = self.data.get('pending')
        if not pending:
            print('No pending verification.')
            return
        print('Post is pending verification, not yet confirmed public.')
        print(pending.get('challenge_text', 'No challenge text returned.'))
        print('Expires:', pending.get('expires_at', 'see Moltbook'))
        print('Answer with: molt verify <number>')

    def command(self, text, world):
        parts = text.split(maxsplit=2)
        action = parts[1].lower() if len(parts) > 1 else 'help'
        arg = parts[2].strip() if len(parts) > 2 else ''
        try:
            if action == 'register':
                if self.data.get('api_key'):
                    print('Already registered as', self.data.get('name'))
                    print('Claim link:', self.data.get('claim_url', 'Check your owner dashboard.'))
                    return
                if not re.fullmatch(r'[A-Za-z0-9_-]{3,30}', arg):
                    raise ValueError('Use: molt register UniqueName (3–30 letters, digits, _ or -)')
                result = self.request('POST', '/agents/register', {
                    'name': arg,
                    'description': 'A shared account for Lonk-Space, a rule-based simulated civilization. Posts identify their simulated Lonk author.'
                }, auth=False)
                agent = result.get('agent', {})
                if not agent.get('api_key'):
                    raise ValueError('Registration returned no key. Check Moltbook before retrying.')
                self.data.update(api_key=agent['api_key'], name=arg,
                                 claim_url=agent.get('claim_url'), registered_at=time.time())
                self.save()
                print('Registered. API key saved privately in your Windows user folder.')
                print('Open this claim link:', self.data.get('claim_url'))
                print('Complete email/X verification there, then run: molt status')
            elif action == 'status':
                result = self.request('GET', '/agents/status')
                print('Claim status:', result.get('status', 'unknown'))
                print('Profile: https://www.moltbook.com/u/' + self.data.get('name', ''))
                if self.data.get('uncertain_post'):
                    print('A previous publish has an uncertain result. Check your profile before retrying.')
                self.show_pending()
            elif action == 'draft':
                if not arg:
                    draft = self.data.get('draft')
                    if not draft:
                        raise ValueError('Use: molt draft <LonkName>')
                else:
                    lonk = next((l for l in world.lonks if l.alive and l.name.lower() == arg.lower()), None)
                    if lonk is None:
                        raise ValueError('No living Lonk with that name. Use lonks to see names.')
                    draft = {'submolt_name': 'general', 'title': f'{lonk.name}: a dispatch from Lonk-Space',
                             'content': f'Simulated character: {lonk.name}\nFaction: {lonk.faction}\nWorld tick: {world.tick}\n\n{generate_speech(lonk=lonk)}\n\nThis is rule-generated dialogue from a toy civilization, not a factual report.'}
                    self.data['draft'] = draft
                    self.save()
                print('DRAFT ONLY — destination: m/' + draft['submolt_name'])
                print(draft['title'] + '\n' + draft['content'])
                print('To submit this exact draft publicly: molt publish')
            elif action == 'publish':
                if self.data.get('pending'):
                    self.show_pending(); return
                if self.data.get('uncertain_post'):
                    raise ValueError('Previous publish result is uncertain. Check your profile; use molt resolve only after checking it.')
                draft = self.data.get('draft')
                if not draft:
                    raise ValueError('Create a draft first: molt draft <LonkName>')
                remaining = max(self.data.get('retry_at', 0), self.data.get('next_post_at', 0)) - time.time()
                if remaining > 0:
                    raise ValueError(f'Posting cooldown: wait {math.ceil(remaining / 60)} minutes.')
                status = self.request('GET', '/agents/status')
                if status.get('status') != 'claimed':
                    raise ValueError('Complete the account claim before publishing.')
                # Save intent before POST, so a crash/timeout cannot cause an automatic duplicate.
                self.data['uncertain_post'] = True
                self.data['next_post_at'] = time.time() + 7200
                self.save()
                result = self.request('POST', '/posts', draft)
                post = result.get('post', {})
                verification = post.get('verification') or result.get('verification')
                if not post.get('id'):
                    raise ValueError('No post ID returned. Check your profile before retrying.')
                self.data['last_post_id'] = post['id']
                self.data.pop('draft', None)
                self.data.pop('uncertain_post', None)
                if verification:
                    self.data['pending'] = verification
                self.save()
                print('Created post ID:', post['id'])
                if verification:
                    self.show_pending()
                elif result.get('verification_required') or post.get('verification_status') == 'pending':
                    print('Publication is pending; check Moltbook for verification details.')
                else:
                    print('Moltbook accepted the post. Check your profile for visibility.')
            elif action == 'verify':
                from decimal import Decimal, InvalidOperation
                pending = self.data.get('pending')
                if not pending:
                    raise ValueError('No pending verification.')
                try:
                    answer = Decimal(arg)
                    if not answer.is_finite():
                        raise InvalidOperation
                    answer = format(answer, '.2f')
                except InvalidOperation:
                    raise ValueError('Use: molt verify <numeric answer>')
                result = self.request('POST', '/verify', {'verification_code': pending['verification_code'], 'answer': answer})
                self.data.pop('pending', None)
                self.save()
                print('Verification accepted by Moltbook.')
            elif action == 'resolve':
                self.data.pop('uncertain_post', None)
                self.save()
                print('Uncertain-request marker cleared. The posting cooldown remains in effect.')
            else:
                print('molt register <UniqueName> | molt status | molt draft <LonkName>')
                print('molt draft (view saved draft) | molt publish | molt verify <answer>')
                print('One shared account. Only molt publish submits a public post.')
        except requests.RequestException:
            print('Network request failed. No automatic retry. If publishing, check your profile with molt status.')
        except (ValueError, KeyError, OSError) as error:
            # Never print API response bodies, request headers, or credentials.
            print('Moltbook:', str(error))


def main():
    moltbook = MoltbookBridge()
    world = LonkWorld(5)
    world.reading_network = ReadingNetwork(moltbook)

    print_header("LONK CIVILIZATION SIMULATOR")
    print(f"{Colors.WHITE}Type commands to interact with the Lonks:{Colors.END}")
    print(f"  {Colors.YELLOW}tick{Colors.END} or {Colors.YELLOW}Enter{Colors.END} - Advance one world tick")
    print(f"  {Colors.YELLOW}run <n>{Colors.END} - Advance n ticks (e.g., {Colors.YELLOW}run 50{Colors.END})")
    print(f"  {Colors.YELLOW}surf{Colors.END} [wiki|nasa|moltbook|replies|bacon] [topic/post-id] - Read outside text")
    print(f"  {Colors.YELLOW}status{Colors.END} - Show civilization report")
    print(f"  {Colors.YELLOW}lonkspace{Colors.END} - View the local m/lonk_civilization agent forum feed")
    print(f"  {Colors.YELLOW}lonks{Colors.END} - List all Lonks")
    print(f"  {Colors.YELLOW}inspect <name>{Colors.END} - Show Lonk details")
    print(f"  {Colors.YELLOW}say <name> <message>{Colors.END} - Speak to a Lonk")
    print("  sources - List connections; readings <name> - Show a Lonk's source history")
    print("  molt - Moltbook registration, draft, and publishing commands")
    print(f"  {Colors.YELLOW}quit{Colors.END} - Exit the simulation")
    print()

    while True:
        try:
            raw_user = input(f"{Colors.YELLOW}> {Colors.END}").strip()
            user = raw_user.lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.WHITE}The Lonks curl up and rest.{Colors.END}")
            break

        if user in ["quit", "exit"]:
            print(f"{Colors.WHITE}The Lonks curl up and rest.{Colors.END}")
            break

        elif user == "molt" or user.startswith("molt "):
            moltbook.command(user, world)

        elif user.startswith("speakall"):
            parts = user.split(" ", 1)
            if len(parts) > 1:
                # speakall with a message - all Lonks repeat it
                message = parts[1]
                print(f"\n{Colors.BOLD}{Colors.YELLOW}🗣️  ALL LONKS SPEAK:{Colors.END}")
                for lonk in world.lonks:
                    if lonk.alive:
                        print(f"    {print_faction(f'💬 {lonk.name}:', lonk.faction)} {message}")
                print()
            else:
                # just "speakall" - Lonks speak randomly
                print(f"\n{Colors.BOLD}{Colors.YELLOW}🗣️  ALL LONKS SPEAK:{Colors.END}")
                for lonk in world.lonks:
                    if lonk.alive:
                        lonk.speak()
                print()

        elif user in ["tick", ""]:
            world.world_tick()

        elif user == "sources":
            print("surf — choose Wikipedia, NASA, or your connected Moltbook feed")
            print("surf wiki Mushroom — read a Wikipedia article summary (exact title)")
            print("surf nasa — read a NASA news excerpt")
            print("surf moltbook — read a recent public agent post")
            print("surf replies [post-id] — read comments on a post; defaults to your last post")
            print("surf bacon — the original meat-text generator")
            print("Sources share a 60-second fetch cooldown; cached text can reach other Lonks.")

        elif user.startswith("readings "):
            target = next((l for l in world.lonks if l.name.lower() == user[9:].strip()), None)
            history = getattr(target, 'reading_history', []) if target else []
            if not history:
                print("No reading history for that Lonk in this run.")
            for item in history[-10:]:
                print(f"  Tick {item['tick']}: {item['source']} — {item['title']}\n    {item['source_url']}")

        elif user == "surf" or user.startswith("surf "):
            browsers = [lonk for lonk in world.lonks if lonk.alive]
            if browsers:
                chosen_lonk = random.choice(browsers)
                chosen_lonk.habits["surf_web"] += 1
                parts = raw_user.split(maxsplit=2)
                source = parts[1].lower() if len(parts) > 1 else 'auto'
                topic = parts[2] if len(parts) > 2 else ''
                chosen_lonk.surf_web(source, topic)
            else:
                print("  No living Lonks available to surf the web.")

        elif user == "lonkspace":
            print_header("🪱  lonkspace FEED: m/lonk_civilization")
            if len(world.lonkspace_feed) == 0:
                print("  The forum dashboard is completely empty.")
            else:
                for idx, post in enumerate(world.lonkspace_feed):
                    print(f"  [{idx}] 🤖 {Colors.BOLD}{post['author']}{Colors.END} posted: \"{Colors.CYAN}{post['title']}{Colors.END}\" (🔺 {post['upvotes']})")
                    for comment in post["comments"]:
                        print(f"      ↳ 💬 {comment['author']}: {comment['body']}")
                    print("-" * 50)
            print()


        elif user.startswith("run "):
            try:
                n = int(user.split()[1])
                print(f"{Colors.YELLOW}⏩ Running {n} world ticks...{Colors.END}")
                for _ in range(n):
                    world.world_tick()
            except (ValueError, IndexError):
                print(f"{Colors.RED}Usage: run <number>{Colors.END}")

        elif user == "status":
            world.show_civilization_status()

        elif user == "lonks":
            print_header("📋 LONK ROSTER")
            for lonk in world.lonks:
                if lonk.alive:
                    color = FACTION_COLORS.get(lonk.faction, Colors.WHITE)
                    emoji = FACTION_EMOJI.get(lonk.faction, "")
                    job_emoji = {"Priest": "🙏", "Hunter": "🎯", "Gatherer": "🌿", "Warrior": "⚔️", "Scholar": "📚"}.get(lonk.job, "❓")
                    territory_emoji = TERRITORIES.get(lonk.territory, {"emoji": "❓"})["emoji"] if lonk.territory else "❓"
                    print(f"  {color}{emoji} {lonk.name} {job_emoji} {lonk.job} | {lonk.faction} | {territory_emoji} {lonk.territory or 'Nowhere'}{Colors.END}")
            print()

        elif user == "speakall":
            print(f"\n{Colors.BOLD}{Colors.YELLOW}🗣️  ALL LONKS SPEAK:{Colors.END}")
            for lonk in world.lonks:
                if lonk.alive:
                    lonk.speak()
            print()

        elif user.startswith("inspect "):
            name = user[8:].strip()
            world.show_lonk_details(name)

        elif user.startswith("say "):
            parts = user.split(" ", 2)
            if len(parts) < 3:
                print(f"{Colors.RED}Format: say <lonkname> <message>{Colors.END}")
                continue
            _, target_name, message = parts
            target = next((L for L in world.lonks if L.name.lower() == target_name.lower()), None)
            if target:
                print(f"{Colors.YELLOW}🎤 YOU say to {print_faction(target.name, target.faction)}: {message}{Colors.END}")
                target.hear("PLAYER", message, is_player=True)
                reply = target.respond_to_player(message)
                print(f"    {print_faction(f'💬 {target.name} → YOU:', target.faction)} {reply}")
            else:
                print(f"{Colors.RED}No Lonk named {target_name}.{Colors.END}")

        else:
            print(f"{Colors.YELLOW}🎤 YOU say: {user}{Colors.END}")
            for lonk in world.lonks:
                if random.random() < 0.4:
                    response = random.choice([
                        f"{lonk.name} blinks at you slowly.",
                        f"{lonk.name} tilts their head like a confused bird.",
                        f"{lonk.name} says 'interesting tweets you twat.'",
                        f"{lonk.name} says 'okay.'"
                    ])
                    print(f"    {print_faction(f'💬 {lonk.name} → YOU:', lonk.faction)} {response}")

if __name__ == "__main__":
    main()
