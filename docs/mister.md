# MISTER.md — Developer Journal & Progress Log

## Phase 0: Setup & Prep
**Status: COMPLETED**

### Progress
- Created project documentation: `README.md`, `tasks.md`, and `mister.md`.
- Initialized Git repository and `.gitignore` for Python, Telethon, and SQLite.
- Created virtual environment (`venv`) and installed initial requirements.
- Established full directory architecture:
  - `/bot`, `/core`, `/data`, `/docs`, `/providers`, `/services`, `/utils`.
- Created `main.py`, `config.py`, and `container.py` skeleton files.

### Bugs / Issues
- **ResolutionImpossible error:** During pip install, aiogram 3.4.1 conflicted with aiofiles 23.1.0.

### Fixes / Solutions
- Upgraded aiofiles to 23.2.1 in requirements.txt to align with aiogram's internal requirements.

---

## Phase 1: MVP — Basic Reposter Bot
**Status: COMPLETED (MVP ACHIEVED)**

### 1.1 User Session Input
- **Progress:**
  - Created `bot/handlers.py`, `bot/routers.py`, and `bot/states.py`.
  - Implemented FSM to track `SessionUpload.waiting_for_input`.
  - Created `services/session_manager.py` and implemented `save_session_file` with `aiofiles`.
  - Linked the Mouth to its Short-term Memory (FSM).
- **Bugs / Issues:**
  - Bot didn't "remember" the user was uploading (needed FSM).
  - No "Ears" to catch the message while in state.
- **Fixes / Solutions:**
  - Added `bot/states.py` and updated handlers to lock the user into the waiting state.

### 1.2 Basic DB Setup (The Vault)
- **Progress:**
  - Created `data/models.py` (User/RepostPair) and `data/database.py` (Async Engine).
  - Implemented `data/repository.py` (UserRepository) with `get_user`, `create_or_update`, and session status toggles.
  - **Librarian Update:** Added `add_repost_pair`, `get_user_pairs`, and `get_all_active_pairs`.
- **Bugs / Issues:**
  - DB blueprints existed but the file wasn't being created on disk.
  - `init_db` wasn't called in the main skeleton.
  - Indentation Error: `add_repost_pair` was initially defined outside the `UserRepository` class.
- **Fixes / Solutions:**
  - Integrated `init_db` into `main.py` so the vault "pours concrete" on startup.
  - Refactored `UserRepository` to include all logic inside the class and fixed missing `RepostPair` imports.

### 1.3 Telethon Client Connection (The Eyes)
- **Progress:**
  - Created `providers/telethon_client.py` with `validate_session` and `start_listener`.
  - Wired `config.py` for API credentials using Pydantic `SecretStr`.
  - Implemented `send_message` logic for the Eyes.
- **Bugs / Issues:**
  - Rule 10 Violation: Using `print()` instead of proper logging.
  - Performance: Validation method was heavy on I/O.
  - **The Blocker:** `run_until_disconnected()` froze the bot's Mouth (polling loop).
- **Fixes / Solutions:**
  - Swapped `print()` for `logging`.
  - Refactored `validate_session` with `async with` context managers.
  - **Mister's Async Fix:** Used `asyncio.create_task` to fire-and-forget the listener into the background (Rule 7).

### 1.4 Bot Commands & 1.5 Core Logic (The Brain)
- **Progress:**
  - Implemented `/start`, `/uploadsession`, `/createpair`, and `/viewpairs`.
  - Created `core/repost/logic.py` with pure cleaning functions (`clean_message_text`).
- **Bugs / Issues:**
  - Service was trying to touch SQL directly (Mutant!).
  - Challenge: Should cleaning logic be in `utils/`?
- **Fixes / Solutions:**
  - Kept logic in `core/` because it's business-specific rules, not generic tools.
  - Added Librarian methods to keep the `services/` layer clean of SQL logic.

### 1.6 Repost Engine & 1.7 Recovery
- **Progress:**
  - Updated `services/repost_engine.py` to bridge the Eyes and the Brain.
  - Implemented `recover_all_listeners` to handle bot reboots.
  - Added `active_clients` dictionary to track sessions by `user_id`.
- **Bugs / Issues:**
  - **The Silent Recovery:** Bot failed to recover listeners because `.session` file paths weren't being recorded in the DB.
  - **The Lambda Trap:** Recovery loop was failing to lock unique pair data into background tasks (closure issue).
- **Fixes / Solutions:**
  - Updated `_save_to_disk` in `session_manager.py` to write the file path to the `UserRepository`.
  - Used default parameter values in the lambda callback to "freeze" unique pair scopes.

### 1.8 Stop Logic & 1.9 Pre-Flight Check
- **Progress:**
  - Implemented `stop_listener` and `/stoppair` command.
  - Completed `main.py` entry point with boot-time exception handling.
- **Bugs / Issues:**
  - **Sequence Logic:** `recover_all_listeners` failed when called before `init_db`.
  - **UnboundLocalError:** `main.py` crashed in `finally` because `bot` wasn't defined yet.
- **Fixes / Solutions:**
  - Reordered `main.py` to birth the `Bot` and `init_db` before any service recovery.

### 1.10 Live Integration & Final Success
- **Progress:**
  - **SUCCESS:** First live text repost confirmed between source and destination!
  - **Stability:** System successfully handles reboots and maintains background listeners.
- **Bugs / Issues:**
  - **CRITICAL - Unauthorized:** Incorrect Bot Token in `.env`.
  - **TimeoutError:** Bot hung for 32s during network flicker; crashed the polling loop.
  - **Database Locked:** `sqlite3.OperationalError` occurred when listener and sender hit the same session file.
- **Fixes / Solutions:**
  - **The Leash:** Added `asyncio.wait_for` to Telethon connections.
  - **Connection Pooling:** Refactored `send_message` to reuse the active client from `active_clients`, killing the locking error.


### 1.11 Stability & DNA Alignment
- **Progress:**
  - Implemented command filtering in `bot/handlers.py` to prevent "Command-as-Data" errors.
  - Aligned `services/` layer with `config.py` data types (int/str vs SecretStr).
  - Cleaned and re-seeded the Vault for a 100% healthy baseline.
- **Bugs / Issues:**
  - **AttributeError:** `str` or `int` object has no attribute `get_secret_value` (DNA mismatch).
  - **ValueError:** `Cannot find any entity corresponding to "/viewpairs"`. The Nervous System tried to "watch" a command as a channel.
  - **Task Exception:** Background tasks were crashing silently due to unhandled entity resolution.
- **Fixes / Solutions:**
  - **Usage Alignment:** Removed `.get_secret_value()` calls for non-SecretStr variables.
  - **The Command Shield:** Added a `.startswith("/")` check in the Mouth's destination handler to reject commands as channel IDs.
  - **Wipe & Reset:** Purged the SQLite file to remove "corrupt" channel names injected during faulty testing.

### Status
- **Current State:** MVP achieved. Text reposting is functional and resilient.
- **Next Task:** Phase 2 - Media support (Photos/Videos) and `destination_id` sanitation for `https://t.me` links.



## Phase 2: Sensory Evolution & The Immune System
**Status: IN PROGRESS (BLOCKED)**

### 2.1 Media Support & Engine Refactor

### Progress
- Refactored `services/repost_engine.py` to support media (Photos, Videos, Documents) in addition to text.
- Implemented in-memory media processing to avoid temporary file clutter and disk pollution.
- Extended Telethon provider capabilities to handle non-text payloads.

### Bugs / Issues
- **UNVERIFIED IMPLEMENTATION:** Media reposting logic has not yet been validated in live conditions.
- **Systemic Blocker:** Media testing cannot proceed because repost pairs cannot be created or viewed due to Gatekeeper restrictions.

### Fixes / Solutions
- Integrated `download_media` (returning raw bytes) and `send_file` into the Telethon provider to enable full message replication.
- Deferred live media validation until repost pair creation (`/createpair`) and inspection (`/viewpairs`) are unblocked.

---

### 2.2 The Gatekeeper (Middleware)

### Progress
- Created `bot/middleware.py` implementing `SessionGuardMiddleware`.
- Introduced a centralized access-control layer to protect session-dependent commands.

### Bugs / Issues
- **ModuleNotFoundError:** Bot crashed on startup due to incorrect imports referencing `database.engine` instead of `data.database`.
- **Critical Blocker – Access Deadlock:**  
  The Gatekeeper is currently preventing access to core commands (`/createpair`, `/viewpairs`) even when valid session files exist.
- **The Access Contradiction:** Users receive "Access Denied" immediately after successful session uploads due to database commit latency.
- **Confusing UX:** Initial denial messages used metaphorical or technical language that did not guide users toward resolution.

### Fixes / Solutions
- **Architecture Alignment:** Corrected middleware imports to reflect the actual `data/` directory structure.
- **The Double-Check Logic:** Updated the Gatekeeper to validate access using both:
  - The Database session state
  - The Physical Disk (`data/sessions/{user_id}.session`)
- **UX Refactor:** Rewrote all denial responses to be clear, professional, and action-oriented.

> **NOTE:** Despite these fixes, access inconsistencies persist and are actively blocking Phase 2 validation.

---

### 2.3 Librarian Expansion (Repository Updates)

### Progress
- Expanded `UserRepository` in `data/repository.py` to support session lifecycle management.

### Bugs / Issues
- **AttributeError:** `UserRepository` lacked the `update_session_string` method, causing `SessionManager` to crash during session uploads.

### Fixes / Solutions
- Implemented `update_session_string`.
- Added an explicit `await self.session.commit()` to ensure session metadata is permanently written to the Vault.

---

### Status
- **Current State:**  
  Media reposting logic is implemented but **cannot be tested** due to Gatekeeper access deadlock.
- **Primary Blocker:**  
  `SessionGuardMiddleware` is preventing repost pair creation and inspection.
- **Next Task:**  
  Resolve Gatekeeper access logic and confirm path synchronization between:
  - `SessionManager` session saving
  - `SessionGuardMiddleware` disk + DB validation  
  Once unblocked, proceed immediately to **live media repost testing**.


## Phase 2: Sensory Evolution & The Immune System
**Status: COMPLETED (STABILIZED)**

### 2.4 The Path-Soul Crisis (Identity Resolution)
**Progress:**
- Refactored the bridge between the **Librarian** (DB) and the **Eyes** (Telethon) to solve the "Not a valid string" error.
- Successfully implemented a **Session Resolver** in the Service layer to distinguish between file paths and Base64 strings.
- Updated `repost_engine.py` to handle absolute pathing for `.session` files stored in `data/sessions/`.
- **The Universal Matcher:** Updated the `_handle_new_message` reflex arc to check both `message.chat_id` and `chat.username`, ensuring reposts trigger regardless of how the channel is identified.

**Bugs / Issues:**
- **ValueError (Not a valid string):** Telethon choked because it tried to read a long Windows file path as a Base64 session string.
- **Architectural Leak:** Attempted to put path-checking logic inside the **Provider**, violating **Rule 11** (Dumb Providers).
- **The ID Mismatch:** The engine saw messages but didn't repost because it was looking for specific IDs while the stream provided usernames.

**Fixes / Solutions:**
- **Rule 11 Restoration:** Stripped all logic out of `telethon_client.py`. It is now a "Dumb Pipe" that just accepts whatever session data the Service gives it.
- **The Service Resolver:** Created `_determine_session_type` in `RepostService` to decide if it should send a `StringSession` or a raw file path to the Eyes.

### 2.5 Vault Sanitation & Locking (The Burn Notice)
**Progress:**
- Implemented the **"Burn Notice"** command: `/deleteall`.
- Added `delete_all_user_pairs` to the `UserRepository` and `RepostService` to clear database clutter.
- Added a **Safety Net** to the boot sequence (`recover_all_listeners`) using `try/except` to prevent a single "broken soul" from crashing the entire organism.

**Bugs / Issues:**
- **The Clutter Bug:** Users ended up with 6+ duplicate pairs for the same source, causing loop-exhaustion.
- **Database Locked (OperationalError):** SQLite seized up because the Bot (SQLAlchemy) and Telethon (SQLite) tried to touch the same session file simultaneously.

**Fixes / Solutions:**
- **The Clean Slate:** Added `/deleteall` to wipe the user's ledger and allow a fresh start.
- **The Resurrection Shield:** Wrapped the recovery loop so the bot ignores corrupt pairs and finishes booting.
- **Lock Management:** Identified that "Database Locked" is caused by ghost `python.exe` processes; implemented connection reuse to minimize file-locking conflicts.

---

### Status
- **Current State:** Phase 2 achieved. Media reposting is live, duplicates are purgeable, and Rule 11 architecture is restored.
- **Milestone:** The bot can "see" a photo in a source and "blink" it to a destination without losing the path to its "soul."
- **Next Task:** Phase 3 - Multi-User Stability & UX Polish.



---

## Phase 2: Sensory Evolution & The Immune System (Continuation)
**Status: COMPLETED**

### 2.6 The Global Gaze (Listener Optimization)
**Progress:**
- Refactored `TelethonProvider.start_listener` to use a **Global Gaze**. Instead of one listener per pair, it now runs **one listener per user session**.
- Moved the "Filtering" logic from the Provider to the **Nervous System** (`RepostService`).
- **Handshake Fix:** Aligned the argument signatures between the Service and the Provider to prevent `TypeError` during pair creation.

**Bugs / Issues:**
- **TypeError (Takes 4 but 5 given):** The Service was still trying to hand the `source_id` to the Provider after the Provider was upgraded to be "source-blind."
- **Listener Exhaustion:** Running multiple listeners on the same session file was causing "Database Locked" errors and high CPU spikes.

**Fixes / Solutions:**
- **Signature Sync:** Removed `source_id` from the `start_listener` call in `repost_engine.py`.
- **Architectural Shift:** The bot now opens its eyes once and checks the incoming message against the entire database ledger in one pass.

### 2.7 Librarian Memory Recovery (The Missing Strand)
**Progress:**
- Updated `data/repository.py` with `get_all_active_users_with_pairs` to support the new global listener architecture.
- Implemented a **Duplicate Guard** in the Librarian to prevent "Clutter Pairs" from entering the Vault.

**Bugs / Issues:**
- **CRITICAL - AttributeError:** The organism failed to boot because `UserRepository` lacked the method to fetch unique active users.
- **The Clutter Bug (Revived):** Users were able to add the same Source -> Destination link multiple times, leading to duplicate reposts of the same message.

**Fixes / Solutions:**
- **DNA Insertion:** Added the missing `distinct()` query to the repository to return a clean list of user IDs for recovery.
- **Integrity Check:** Added a `select` check in `add_repost_pair` to verify a link doesn't already exist before committing it to the Vault.

---

### Status
- **Current State:** **MVP 2.0 ACHIEVED.** The bot is now architecturally perfect for multiple users and multiple pairs.
- **Milestone:** Successfully handled the first "Global Blink" where one session manages multiple routing rules without conflict.
- **Next Task:** Phase 3 - Multi-User Stability, UX Polish, and Command Throttling.


## Phase 3: The Synchronized Organism & Media Mastery
**Status: IN PROGRESS**

### 3.1 The Synchronized Handshake (State Management)
**Progress:**
- Refactored the **Nervous System** (`RepostService`) to ensure the **Vault** (DB) and the **Eyes** (Telethon) are always in sync.
- Implemented the **Status Guard**: The reflex arc now explicitly checks `is_active` before any blink occurs, preventing "ghost reposting."
- Integrated the **"Wake Up" Handshake**: The `/stoppair` and `/startpair` commands now physically trigger the listener's lifecycle, ensuring the bot doesn't stay dormant when it should be watching.

**Bugs / Issues:**
- **The Ghost Signal:** Even when a pair was "stopped" in the DB, the background listener was still firing because it wasn't checking the latest state.
- **The Dormant Eye:** Activating a pair didn't always wake up the listener if it was the user's first active pair after a period of total inactivity.

**Fixes / Solutions:**
- Added a `if not p.is_active: continue` check inside the message handler loop.
- Updated `activate_pair` in the Service layer to force-call `start_listener`, ensuring the background task is alive the moment the switch is flipped.

### 3.2 The Album Buffer (Media Group Mastery)
**Progress:**
- Successfully implemented an **Asynchronous Waiting Room** for media groups.
- Upgraded the **Eyes** (Telethon Provider) to support `send_file` for albums, allowing the bot to bundle photos and videos into a single post.
- **Smart Captioning:** The bot now extracts the caption from the first message of an album to prevent "Triple-Caption Spam."

**Bugs / Issues:**
- **The Stuttering Repost:** Sending an album of 3 photos resulted in 3 separate messages with duplicate captions.
- **Database Locked (MTProtoSender):** Rapid-fire messages from an album caused Telethon to attempt multiple simultaneous writes to the `.session` file.
- **Task Destruction:** Closing a listener roughly caused `Task was destroyed but it is pending!` errors.

**Fixes / Solutions:**
- **The 1-Second Heartbeat:** Implemented `asyncio.sleep(1.0)` in a dedicated `_process_album_after_delay` task. This buffers incoming `grouped_id` messages before executing a single blink.
- **Graceful Sleep:** Added a `0.2s` cooldown and an explicit `await client.disconnect()` in the Provider to let Telethon finish its "paperwork" before the session closes.
- **The Tray Logic:** Shifted the Provider logic to detect if it's being handed a `list` (Album) or a single object, and choose the correct Telethon method accordingly.

---

### Status
- **Current State:** **Media Group Support ACHIEVED.** The bot now handles albums with professional precision.
- **Milestone:** The transition from "Physical Connection" (1 listener per pair) to "Logic-Based Routing" (1 listener per user) is now 100% stable.
- **Next Task:** Phase 3.3 - Content Filters (Link Removal & Caption Cleaning).



### 3.3 Content Filters & Schema Evolution (The Alembic Era)
**Progress:**
- **Dynamic Schema Management:** Integrated **Alembic** for database migrations. We no longer need to delete the "Vault" to add new features; the bot now performs "Live Surgery" on its own tables.
- **Filtering Anatomy:** Added `filter_type` and `replacement_link` columns to the `repost_pairs` table, allowing users to choose how the bot handles external links.
- **Nervous System Integration:** Successfully updated the **Repost Engine** (`repost_engine.py`) to call the `MessageCleaner` before every blink.
- **The "Type-Aware" Eye Fix:** Refined the **Telethon Provider** to handle mixed content types (Text-only vs. Media-Albums) within the same logic path.

**Bugs / Issues:**
- **The "No Such Column" Tantrum:** Adding new fields to the Python Model caused the bot to crash because the physical `.db` file was outdated.
- **Empty Box Syndrome:** Sending a text message with a link caused `Blink failed: Cannot use [] as file` because the bot was looking for media that didn't exist in the "box."
- **TLObject Mismatch:** Telethon threw errors when receiving raw strings for destinations instead of resolved "Peers" (IDs or Usernames).

**Fixes / Solutions:**
- **Alembic Alignment:** Synced the `alembic.ini` path with `config.py` to ensure migrations happen in the `/data` folder. Used `alembic upgrade head` to finalize the schema.
- **The Filter Call:** Inside `_execute_repost`, we now loop through all messages in a bundle and overwrite `msg.message` with the output of `MessageCleaner.clean(msg.message, p.filter_type, p.replacement_link)`.
- **The Media-Check Guard:** Updated `send_message` in the Provider to check `if files:`. If empty, it falls back to a text-based `send_message` rather than a file-based one.
- **Target Digit-Check:** Implemented a check to convert numeric strings to `int` before passing them to Telethon, ensuring the "Eyes" focus on the correct destination.

---

### Status
- **Current State:** **Content Filtering Architecture BUILT & INTEGRATED.** The bot now "cleans" messages automatically based on user-defined rules.
- **Milestone:** Successfully transitioned the project to a **Version-Controlled Database** state and established a stable processing pipeline for albums and text.
- **Next Task:** Phase 3.4 - Stability & Error Handling (Addressing the "Signal Ghost" timeouts and adding retry logic).