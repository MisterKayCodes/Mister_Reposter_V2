# Mister Reposter V2

A "set-and-forget" Telegram bot that connects to your personal Telegram account (via Telethon) and automatically copies messages from one channel to another. Fully inline-button-driven interface — the only slash command is `/start`.

---

## Features

### Channel Reposting
- Configure up to **4 repost pairs** (source -> destination)
- Supports **public and private channels** (via invite links)
- Handles **all media types**: text, photos, videos, documents, and albums
- **Album grouping**: media groups are bundled and sent as a single album, not separate messages
- **Content filters**: keep original links, remove all links, or replace links with your own

### Scheduling
- **Instant mode**: messages are forwarded in real time as they arrive
- **Scheduled mode**: batch messages at intervals from 5 minutes to 24 hours
- **Start-from-message backfill**: for scheduled pairs, optionally fetch and forward historical messages from a specific message ID onward

### Reliability & Safety
- **Error tracking**: each pair tracks consecutive errors; auto-disables after 5 failures
- **Pair health status**: `Active`, `Paused`, or `Error` — visible in the dashboard
- **FloodWait protection**: handles Telegram rate limits with automatic backoff and retry (up to 3 attempts)
- **Duplicate detection**: in-memory tracker using message ID + media hash (LRU cache, 500 entries per pair) prevents double-posting
- **Confirmation preview**: shows a full summary of source, destination, filter, schedule, and start message before activating a new pair
- **Media cache**: stores message references for scheduled reposts with 24-hour eviction to prevent stale file references
- **file_id caching**: remembers Telegram file IDs for 7 days to avoid re-uploading the same media
- **Auto-recovery**: all active listeners resume automatically on bot restart

### Permissions
- **Admin system**: `ADMIN_IDS` list in `config.py` controls privileged access
- **Logs**: only admin users can view application logs; the Logs button is hidden for non-admins

### User Interface
- Fully **callback-button-driven** — no slash commands except `/start`
- Main menu shows pair count, active/error status, and session state
- Pairs dashboard shows status badges, error counts, filter mode, and schedule per pair
- Upload Session button hidden when session is already linked
- Two-step confirmation for destructive actions (delete pair, delete all)

### Observability
- **In-bot logs**: admin users can view the last 25 log entries directly in Telegram
- Circular log buffer (100 entries) attached to Python's root logger
- Refresh button for live log updates

---

## Architecture: The Living Organism

The project follows a **service-oriented architecture** with strict separation of concerns.

| Layer | Folder | Role |
|-------|--------|------|
| **The Mouth** | `bot/` | Telegram bot interface — handlers, FSM states, middleware, keyboards |
| **The Nervous System** | `services/` | Orchestration layer connecting bot to database, Telethon, and cache |
| **The Eyes** | `providers/` | Raw Telegram API communication via Telethon |
| **The Brain** | `core/` | Pure functions for text processing and channel input resolution |
| **The Vault** | `data/` | Database models, engine setup, and repository pattern |
| **The Skeleton** | `main.py` | Application entry point — initializes DB, recovers listeners, starts polling |
| **The DNA** | `config.py` | Pydantic-validated environment configuration + admin IDs |
| **Utilities** | `utils/` | Cross-cutting concerns (log buffer) |
| **Documentation** | `docs/` | Technical journal (mister.md) and personal dev log (dev_log.md) |

---

## Project Structure

```
Mister_ReposterV2/
|
|-- bot/                        # The Mouth (Telegram Interface)
|   |-- handlers/
|   |   |-- menu.py             # /start, main menu, delete-all
|   |   |-- pairs.py            # Create pair flow, toggle, delete, confirm
|   |   |-- session.py          # Session upload flow
|   |   |-- logs.py             # Admin-only log viewer
|   |   |-- utils.py            # Shared render helpers
|   |-- keyboards.py            # All inline keyboard builders
|   |-- states.py               # FSM state definitions
|   |-- middleware.py            # Command gatekeeper
|   |-- routers.py              # Router registration
|
|-- services/                   # The Nervous System
|   |-- repost_engine.py        # Core repost logic, scheduling, listeners
|   |-- session_manager.py      # Session file handling
|   |-- media_cache.py          # Media reference + file_id caching
|
|-- providers/                  # The Eyes
|   |-- telethon_client.py      # Telethon client management
|
|-- core/                       # The Brain
|   |-- repost/
|   |   |-- resolver.py         # Channel input parser (pure functions)
|   |   |-- logic.py            # Message cleaning (filter rules)
|
|-- data/                       # The Vault
|   |-- models.py               # SQLAlchemy models (User, RepostPair)
|   |-- repository.py           # UserRepository (all DB access)
|   |-- database.py             # Async engine setup
|   |-- sessions/               # Telethon .session files
|   |-- reposter.db             # SQLite database (auto-created)
|
|-- utils/                      # Utilities
|   |-- log_buffer.py           # Circular log buffer handler
|
|-- migrations/                 # Alembic migrations
|   |-- versions/               # Migration scripts
|
|-- docs/                       # Documentation
|   |-- mister.md               # Technical progress journal
|   |-- dev_log.md              # Personal reflective dev log
|
|-- config.py                   # Settings + ADMIN_IDS
|-- main.py                     # Entry point
|-- requirements.txt            # Python dependencies
|-- alembic.ini                 # Alembic configuration
|-- .env                        # Environment variables (not committed)
```

---

## Database Schema

### users
| Column | Type | Description |
|--------|------|-------------|
| id | BigInteger (PK) | Telegram user ID |
| username | String | Telegram username |
| created_at | DateTime | Account creation timestamp |
| has_active_session | Boolean | Whether a Telethon session is linked |
| session_string | String (nullable) | Base64 session string |

### repost_pairs
| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Auto-incrementing pair ID |
| user_id | BigInteger (FK) | Owner's Telegram user ID |
| source_id | String | Source channel username or numeric ID |
| destination_id | String | Destination channel |
| is_active | Boolean | Whether the pair is actively listening |
| last_reposted_at | DateTime (nullable) | Timestamp of last successful repost |
| filter_type | Integer | 0=keep original, 1=remove links, 2=replace links |
| replacement_link | String (nullable) | Custom link for filter_type=2 |
| schedule_interval | Integer (nullable) | Minutes between flushes; 0/null=instant |
| start_from_msg_id | Integer (nullable) | Message ID for backfill start |
| error_count | Integer | Consecutive error count (resets on success) |
| status | String | "active", "paused", or "error" |

---

## FSM States

| State | Purpose |
|-------|---------|
| `SessionUpload.waiting_for_input` | User is sending a .session file or base64 string |
| `CreatePair.waiting_for_source` | Awaiting source channel input |
| `CreatePair.waiting_for_destination` | Awaiting destination channel input |
| `CreatePair.waiting_for_filter` | Choosing filter mode |
| `CreatePair.waiting_for_replacement` | Entering replacement link (filter_type=2 only) |
| `CreatePair.waiting_for_schedule` | Choosing schedule interval |
| `CreatePair.waiting_for_start_message` | Optionally entering start-from message (scheduled only) |
| `CreatePair.waiting_for_confirmation` | Reviewing pair summary before activation |

---

## Permissions

### Admin IDs
Defined in `config.py` as `ADMIN_IDS`:

```python
ADMIN_IDS: list[int] = [8526011565]
```

### Admin-Only Features
- **Logs**: the "Logs" button is only visible to admin users in the main menu. Non-admin users who somehow trigger the `logs` callback receive an "Access denied" alert.

### User Features (All Users)
- Upload session
- Create, view, toggle, and delete repost pairs
- Delete all pairs

---

## Channel Input Formats

The bot accepts all of the following when specifying source or destination channels:

| Format | Example |
|--------|---------|
| Username | `@channelname` |
| t.me link | `t.me/channelname` |
| Private invite | `t.me/+invite_hash` |
| Private invite (old) | `t.me/joinchat/hash` |
| Private post link | `t.me/c/12345/50` |
| Public post link | `t.me/channelname/50` |
| Numeric ID | `-1001234567890` |
| Forwarded message | (auto-extracts chat ID) |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Telegram Bot API token from @BotFather |
| `API_ID` | Yes | Telegram API ID from my.telegram.org |
| `API_HASH` | Yes | Telegram API hash from my.telegram.org |
| `DATABASE_URL` | No | Defaults to `sqlite+aiosqlite:///data/reposter.db` |

Create a `.env` file in the project root:

```
BOT_TOKEN=your_bot_token_here
API_ID=12345678
API_HASH=your_api_hash_here
```

---

## Setup & Run

```bash
pip install -r requirements.txt
python main.py
```

The bot will:
1. Initialize the database and run migrations
2. Start the health-check web server on port 5000
3. Recover all active listeners from the database
4. Begin polling for Telegram updates

---

## Usage Flow

1. Send `/start` to the bot
2. Tap **Upload Session** to link your Telegram account (.session file or base64 string)
3. Tap **Create Pair** to set up a repost rule:
   - Enter source channel (any supported format)
   - Enter destination channel
   - Choose filter mode (keep/remove/replace links)
   - Choose schedule interval (instant to 24 hours)
   - Optionally set a start-from message (scheduled only)
   - Review the preview and tap **Confirm**
4. Tap **My Pairs** to view, pause/resume, or delete pairs
5. Admin users can tap **Logs** to view recent application logs

---

## Key Design Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_PAIRS` | 4 | Maximum repost pairs per user |
| `MAX_ERRORS_BEFORE_DISABLE` | 5 | Consecutive errors before auto-disable |
| `FLOOD_WAIT_MAX_RETRY` | 3 | Max retry attempts for FloodWait |
| `DEDUP_CACHE_SIZE` | 500 | LRU cache entries per pair for dedup |
| `MediaCache max_age` | 24 hours | Message bundle eviction TTL |
| `file_id cache TTL` | 7 days | file_id reference eviction TTL |

---

## Dependencies

- **aiogram 3.4.1** — Telegram Bot API framework (async, FSM, middleware)
- **telethon 1.36.0** — Telegram MTProto client for user account operations
- **SQLAlchemy 2.0.25** — Async ORM for database access
- **aiosqlite 0.19.0** — Async SQLite driver
- **alembic 1.13.0** — Database migration management
- **pydantic / pydantic-settings** — Configuration validation
- **aiohttp** — Health-check HTTP endpoint

---

## Development Rules

1. **Known State**: every variable must be explicitly set before use
2. **Durability**: all critical state must survive restarts
3. **Single Responsibility**: each module does one thing
4. **Explicit Logic**: no implicit behavior or magic
5. **Idempotency**: operations must be safe to repeat
6. **Resilience**: graceful handling of all failures
7. **Observability**: everything must be loggable and inspectable

---

REVISION: 4.1.0
STATUS: OPERATIONAL
