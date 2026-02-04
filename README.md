
# Mister_ReposterV2

A Telegram repost bot that allows users to copy posts from one channel or group to another with scheduling, filtering, and subscription management.

---

## Phase 0: Setup & Preparation

This project is currently in the initial setup and preparation phase. The core goals here are to establish the foundation for a scalable and maintainable repost bot.

### Project Goals for Phase 0

- Initialize a Git repository with proper `.gitignore` for Python, Telethon, SQLite, and related files.
- Create a comprehensive `README.md` with project overview and MVP goals.
- Set up a Python virtual environment and pin initial dependencies.
- Create the base folder structure and placeholder files with docstrings and TODO comments to organize the codebase.

### Folder Structure

```

/bot           # Telegram bot handlers, commands, and UI
/core          # Core repost and subscription logic
/data          # Database models, schema, and repository layer
/providers     # Telegram API wrappers, Telethon client integration
/services      # Orchestration, scheduling, session management
/utils         # Helper utilities (logging, validation, media cache)
main.py        # Application entry point
config.py      # Configuration and environment variable loading
container.py   # Dependency injection and wiring

````

### Dependencies (Initial)

- `aiogram==3.4.1` — Telegram bot framework
- `telethon==1.36.0` — Telegram user client for session management and reposting
- `SQLAlchemy==2.0.25` — ORM for database modeling and querying
- `alembic==1.13.0` — Database migrations
- `pytest==7.4.0` — Testing framework
- `python-dotenv==1.0.0` — Environment variable loading
- Additional dependencies for async DB (`aiosqlite`), HTTP requests (`httpx`), and utilities (`loguru`, `orjson`, etc.) will be added as needed.

---

## Next Steps After Phase 0

- Begin implementing core repost logic and subscription management.
- Design and initialize database schema.
- Develop Telegram bot command handlers and UI.
- Build service layers for repost scheduling and session management.
- Write tests for core functionality.

---

## Getting Started

1. Clone the repository (to be created)
2. Set up a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
````

3. Install pinned dependencies:

   ```bash
   pip install -r requirements.txt
   ```
4. Run initial checks and start project scaffolding.

---

## Contact & Contribution

For now, this is a personal project under active development. Contributions and suggestions are welcome once core functionality is stable.

---

*Built with ❤️ by Mister

