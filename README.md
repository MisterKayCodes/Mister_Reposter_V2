# PROJECT: MISTER REPOSTER V2
# LEAD ENGINEER: MISTER
# AMBIENCE: DRAKE - FOCUSED

## OVERVIEW
Mister Reposter V2 is a "set-and-forget" Telegram bot. It connects to your personal Telegram account and automatically copies messages from one channel to another. It is built to be stable, fast, and resilient—meaning if it crashes, it wakes up and keeps working without you touching it.

---

## CORE FEATURES
* MULTI-ACCOUNT: Link your own Telegram session to act as the "sender."
* ONE-STOP LISTENING: One connection manages all your channel links at once to save CPU.
* ALL MEDIA SUPPORTED: Copies text, photos, videos, and documents perfectly.
* AUTO-RECOVERY: If the bot reboots, it automatically restarts all your listeners.
* THE BURN NOTICE: One command (/deleteall) wipes your data for a clean slate.
* CLEAN INPUT: No need to worry about messy links; the bot cleans them for you.

---

## ARCHITECTURE: THE ORGANISM
We use a "Service-Oriented" setup to keep the brain separate from the mouth.



* BOT LAYER (THE MOUTH): Handles the buttons and commands you see in Telegram.
* SERVICE LAYER (THE NERVOUS SYSTEM): The middleman that connects the bot to the database.
* TELETHON LAYER (THE EYES): The actual connection to Telegram that watches for messages.
* DATABASE LAYER (THE VAULT): Where your settings and links are safely stored.
* CORE LAYER (THE BRAIN): Simple logic that cleans text and checks rules.

---

## PROJECT STRUCTURE
Mister_ReposterV2/
│
├── bot/                # The "Mouth" (Telegram Interface)
│   ├── handlers.py     # Command logic (/start, /createpair)
│   ├── middleware.py   # The Gatekeeper (Security check)
│   └── states.py       # FSM (Tracking your steps)
│
├── services/           # The "Nervous System" (Logic Middleman)
│   ├── repost_engine.py# Managing the listeners
│   └── session_service.py # Saving your login files
│
├── providers/          # The "Eyes" (Telegram Connection)
│   └── telethon_client.py # Talking to Telegram servers
│
├── data/               # The "Vault" (Storage)
│   ├── repository.py   # Librarian (Saving/Loading data)
│   ├── models.py       # Database blueprints
│   └── database.py     # The "Concrete Mixer" (DB Setup)
│
├── core/               # The "Brain" (Pure Logic)
│   └── logic.py        # Cleaning links and text
│
├── config.py           # Settings and Secret Keys
├── main.py             # The "Heartbeat" (Startup file)
└── requirements.txt    # Essential tools needed to run
 
---

## SETUP INSTRUCTIONS

1. GET THE FILES:
   git clone https://github.com/yourusername/Mister_ReposterV2.git
   cd Mister_ReposterV2

2. PREPARE THE TOOLS:
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt

3. ADD YOUR KEYS:
   Create a .env file and add your API_ID, API_HASH, and BOT_TOKEN.

4. START THE ENGINE:
   python main.py

---

## COMMAND LIST
/start          - Get started and register.
/uploadsession  - Connect your Telegram account.
/createpair     - Link a "From" channel to a "To" channel.
/viewpairs      - See all your active links.
/stoppair <id>  - Stop a specific link.
/deleteall      - Wipe everything and start fresh.

---

## DEVELOPMENT RULES
* KEEP IT SIMPLE: No complex code where a simple one works.
* BE EXPLICIT: The bot shouldn't guess; it should follow your orders.
* NO LEAKS: Always close connections and clean up data.
* STAY FOCUSED: Every file has one job and stays in its lane.

---
REVISION: 2.5.0
STATUS: OPERATIONAL