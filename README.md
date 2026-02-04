# Mister_ReposterV2

A modular, scalable Telegram repost bot designed to bridge channels using **Telethon** (User API) and **Aiogram** (Bot API). Built with a strict "Genius in a Dark Room" architecture to ensure logic, storage, and interface remain decoupled.

---

## 🚀 Current Status: Phase 1 (MVP) COMPLETED
The bot has successfully achieved MVP status. Core functionality for text-based reposting, session management, and startup recovery is fully operational.

### ✅ Completed in Phase 1
- **Architectural Foundation:** Implemented Folder Anatomy (Core, Data, Bot, Providers, Services).
- **Session Management:** Securely handles StringSessions and `.session` files with background storage.
- **Persistence Layer:** SQLite integration via SQLAlchemy 2.0 with a "Librarian" (Repository) pattern.
- **Non-Blocking Listeners:** Background task orchestration using `asyncio` to allow multi-user handling.
- **Startup Recovery:** Automatic restoration of active repost listeners upon bot reboot.
- **Connection Pooling:** Smart client reuse to prevent "Database is locked" errors in SQLite.

---

## 🛠️ Project Architecture

```text
/bot           # The Mouth: Aiogram handlers, commands, and FSM states.
/core          # The Brain: Pure business logic (Cleaning, filtering).
/data          # The Vault: Models and the Librarian (Repository).
/providers     # The Eyes: Telethon client and external API wrappers.
/services      # The Nervous System: Orchestration and background tasks.
/utils         # The Toolbox: Shared helpers and logging.
main.py        # The Skeleton: Application entry point.
config.py      # The DNA: Pydantic-validated environment settings.
container.py   # The Wiring: Dependency Injection (In Progress).
Use code with caution.

📈 Next Steps (Phase 2)
Media Support: Implementing logic to handle Photos, Videos, and Media Groups.
Link Sanitization: Auto-formatting of source/destination links to raw entities.
Advanced Filtering: Link removal, keyword blacklists, and caption modification.
Deployment: Dockerization and VPS setup with Rule 18 (Safe Deployment Protocol).
⚙️ Getting Started
Clone & Setup:
bash
git clone <repo-url>
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
Use code with caution.

Configuration:
Create a .env file in the root.
Add your BOT_TOKEN, API_ID, and API_HASH.
Run:
bash
python main.py
Use code with caution.

⚖️ Development Rules
This project follows the Level-Up Dev Rulebook (2025):
The System is always in a known state.
Store all critical state in durable storage.
Logic must be explicit and readable.
No "smart" guessing.
Separate business logic from integrations (Rule 11).
Expect failure, design for recovery (Rule 7).




Built with ❤️ by Mister