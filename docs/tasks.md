# Tasks.md — Mister Reposter Bot Roadmap (MVP + Full Project)

---

## 🏁 Project Start (Setup & MVP)

### [ ] 0. Setup & Prep

* Initialize Git repository with `.gitignore` (Python, Telethon, SQLite, etc.)
* Create `README.md` with project overview and MVP goals
* Set up Python environment (virtualenv/venv) and pin dependencies (see full requirements.txt below)
* Create base folder structure:

  ```
  /bot
  /core
  /data
  /docs(mister.md and tasks.md)
  /providers
  /services
  /utils
  main.py
  config.py
  container.py
  ```
* Create placeholder files with docstrings and TODO comments

---

### [ ] 1. MVP — Basic Reposter Bot (Step-by-Step)

#### 1.1 User Session Input

* Implement `/uploadsession` command

  * User sends their Telethon session string or uploads session file
  * Handling the Validation and Storage you listed (`services/session_manager.py`)
  * Validate and securely save session linked to user ID (`data/models.py` User + session info)
  * Store session file on disk or encrypted store (`/data/sessions/{user_id}.session`)

#### 1.2 Basic DB Setup

* Minimal models: User, Session, RepostPair (source channel, destination channel, status)
* Implement basic CRUD for above (`data/repository.py`)

#### 1.3 Telethon Client Connection

* Implement `providers/telethon_client.py`

  * Load user session from storage
  * Connect to Telegram user client
  * Basic error handling (invalid session, login expired)

#### 1.4 Bot Commands for MVP

* `/start` — welcome message with instructions
* `/uploadsession` — handle session input from user
* `/createpair` — prompt user for source channel username or post link, destination channel username
* `/viewpairs` — list user’s repost pairs with minimal info

#### 1.5 Core Repost Logic (Basic)

* `core/repost/logic.py` pure functions

  * Fetch last messages from source channel
  * Copy text messages only (no media yet)
  * Post copied messages to destination channel (no forwarding)

#### 1.6 Repost Engine MVP

* `services/repost_engine.py`

  * On pair creation or bot start, listen for new messages on source channel (using Telethon)
  * Immediately repost new text messages to destination channel
  * Basic error logging and retry (no scheduling yet)

#### 1.7 Run and Test MVP

* Start bot with `main.py`
* Test full user flow: `/start`, `/uploadsession`, `/createpair`, new message triggers repost, `/viewpairs`
* Fix bugs, improve error messages

---

## 🧠 Core — Pure Logic Development (Post-MVP)

### [ ] 2. Enhanced Repost Logic

* Add support for media messages: photos, videos, documents, stickers, polls
* Preserve formatting and captions
* Add link removal and replacement filters

### [ ] 3. Subscription Logic

* Define subscription tiers, trial periods, activation codes
* Check access rights before allowing repost or pair creation

---

## 💾 Data — Persistence Layer (Post-MVP)

### [ ] 4. Extend Database Models & Repository

* Add `FilterRule`, `Subscription`, `ActivationCode` models
* Full CRUD and complex queries

### [ ] 5. Setup Alembic Migrations

---

## 👄 Bot — Telegram Interface (Post-MVP)

### [ ] 6. Bot Commands & UI

* Add inline keyboards for scheduling intervals, start/stop pairs, edit filters
* Add `/redeemcode`, `/subscription`, `/help`

### [ ] 7. Filters Management UI

---

## 🧬 Services — Orchestration Layer

### [ ] 8. Scheduling & Repost Engine

* Add scheduling options (5m, 30m, 2h, 8h, 12h intervals)
* Manual repost range from older posts

### [ ] 9. Session Management Enhancements

### [ ] 10. Notifications Service

---

## 👁️ Providers — External API Wrappers

### [ ] 11. Telethon Client Enhancements

* Media caching, private channel invite parsing

### [ ] 12. Telegram Bot API Wrapper (Optional)

---

## 🛠️ Utils & Helpers

### [ ] 13. Logging, Metrics & Media Cache

---

## 🦴 Skeleton — Bootstrapping & Wiring

### [ ] 14. Application Entry Point (`main.py`)

### [ ] 15. Dependency Injection Container (`container.py`)

---

## ✅ Testing & QA

### [ ] 16. Unit Tests (core logic, filters, subscription)

### [ ] 17. Integration Tests (services + Telethon mocks)

### [ ] 18. Bot Command Tests (aiogram test utilities)

---

## 🚀 Deployment & Monitoring

### [ ] 19. Deployment Scripts (Dockerfile or VPS scripts)

### [ ] 20. Safe Deployment Protocol

### [ ] 21. Monitoring & Alerts

---

## 🔄 Maintenance & Future Work (Flexible)

### [ ] 22. Advanced Filters & Rules

### [ ] 23. Analytics Dashboard (Admin)

### [ ] 24. User Roles & Permissions Enhancements

---

# Full `requirements.txt` for this project

```
aiogram==3.4.1
pydantic==2.5.2
pydantic-settings==2.2.1
SQLAlchemy==2.0.25
alembic==1.13.0
aiosqlite==0.19.0
httpx==0.26.0
taskiq==0.11.7
anyio==4.2.0
loguru==0.7.2
python-dateutil==2.8.2
orjson==3.9.10
telethon==1.36.0
python-dotenv==1.0.0
pytest==7.4.0
pytest-asyncio==0.21.0
black==23.7.0
isort==5.12.0
flake8==6.0.0
aiofiles==23.1.0
```

---

# Notes

* MVP explicitly requires user to **provide their Telethon session string or file**. This cannot be automated or magically detected.
* The roadmap keeps full flexibility for gradual feature add, while ensuring MVP is runnable and testable.
* The tasks use your project anatomy and level-up dev rulebook for maintainability and clean code.

---
