# Mister Reposter V2

**A Telegram Reposting Bot with Self-Healing Architecture**

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

---

## 📖 Overview

Mister Reposter V2 is a sophisticated Telegram bot that automatically reposts messages from source channels to destination channels. Built on an **Organism Model** architecture, it features filtering, scheduling, media handling, and self-healing capabilities that keep your reposting operations running smoothly.

### Key Features

| Feature | Description |
|---------|-------------|
| **🔄 Automatic Reposting** | Watch source channels and repost to destinations |
| **🎯 Smart Filtering** | Keep, Remove, Replace, or Nuke links/usernames |
| **⏰ Flexible Scheduling** | Instant or scheduled intervals (5min - 24hr) |
| **📸 Media Handling** | Full support for photos, videos, documents, albums |
| **🔒 Protected Content** | Download/upload mode for `noforward` media |
| **🩺 Self-Healing** | Autonomic heartbeat detects and fixes stalls |
| **🔁 Loop History** | Restart from beginning when caught up |
| **📊 Real-Time Stats** | Progress tracking with ETA calculations |
| **🌐 REST API** | Full programmatic control via HTTP endpoints |
| **👥 Multi-User** | Admin, premium, and client user tiers |

---

## 🏛️ Architecture

Mister Reposter V2 follows the **Organism Model** — a biological metaphor for clean separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                     SKELETON (main.py)                          │
│         Hybrid Boot: Bot Polling + FastAPI on Port 5555         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   NERVES (services/)                            │
│     RepostEngine • Autonomic • SessionManager • MediaCache      │
└─────────────────────────────────────────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  MOUTH (bot/)   │ │ EYES/HANDS      │ │  MEMORY (data/) │
│                 │ │ (providers/)    │ │                 │
│ • Handlers      │ │                 │ │ • Models        │
│ • Keyboards     │ │ • Telethon      │ │ • Repository    │
│ • Middleware    │ │   Provider      │ │ • Database      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BRAIN (core/)                                │
│          Pure Logic • MessageCleaner • ChannelResolver          │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Can Do | Cannot Do |
|-------|--------|-----------|
| **Mouth** (`bot/`) | Render UI, handle input, call Services | Open DB, contain business logic |
| **Nerves** (`services/`) | Open DB, call Repos, apply rules | Send Telegram messages |
| **Memory** (`data/`) | Define models, execute queries | Contain business logic |
| **Eyes/Hands** (`providers/`) | Talk to Telegram API | Know about business logic |
| **Brain** (`core/`) | Pure logic, text processing | Import aiogram, SQLAlchemy |
| **Utilities** (`utils/`) | Pure functions, logging | Import other layers |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Telegram API ID & Hash (from [my.telegram.org](https://my.telegram.org))
- PM2 (for production deployment)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/Mister_ReposterV2.git
cd Mister_ReposterV2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
# Required
BOT_TOKEN=your_bot_token_here
API_ID=your_api_id
API_HASH=your_api_hash

# Optional
API_KEY=your_api_key_for_rest_api
OWNER_USERNAME=YourUsername
DATABASE_URL=sqlite+aiosqlite:///data/reposter.db
```

### Running

```bash
# Development
python main.py

# Production (PM2)
pm2 start ecosystem.config.js
```

The bot will start with:
- Telegram bot polling
- REST API on port 5555
- Guardian pre-boot checks
- Autonomic heartbeat monitoring

---

## 📁 Project Structure

```
Mister_ReposterV2/
├── main.py                      # Entry point (hybrid bot + API)
├── requirements.txt             # Python dependencies
├── ecosystem.config.js          # PM2 configuration
├── .env                         # Secrets (not in git)
│
├── app/
│   ├── api/                     # 🌐 REST API Layer
│   │   ├── routes.py            # All endpoints
│   │   ├── schemas.py           # Pydantic models
│   │   ├── security.py          # API key auth
│   │   └── server.py            # FastAPI factory
│   │
│   ├── bot/                     # 🗣 Mouth Layer
│   │   ├── keyboards.py         # Reply & inline keyboards
│   │   ├── keyboards_admin.py   # Admin keyboards
│   │   ├── middleware.py        # NetworkRetry, SessionGuard
│   │   ├── routers.py           # Router registration
│   │   ├── states.py            # FSM states
│   │   └── handlers/            # All handlers
│   │       ├── menu.py          # /start, main menu
│   │       ├── session.py       # Session upload
│   │       ├── pairs.py         # Pair creation FSM
│   │       ├── pairs_manage.py  # Toggle, loop, protect
│   │       ├── pairs_client.py  # Client controls
│   │       ├── stats.py         # Stats dashboard
│   │       ├── admin_users.py   # User management
│   │       ├── admin_settings.py# Bot settings
│   │       ├── logs.py          # Log viewer
│   │       ├── alertbot.py      # Inventory alerts
│   │       └── utils.py         # Shared helpers
│   │
│   ├── core/                    # 🧠 Brain Layer
│   │   ├── config.py            # Pydantic settings
│   │   └── repost/
│   │       ├── logic.py         # MessageCleaner
│   │       └── resolver.py      # Channel input parser
│   │
│   ├── data/                    # 💾 Memory Layer
│   │   ├── database.py          # Async engine, session factory
│   │   ├── models.py            # SQLAlchemy ORM
│   │   ├── repository.py        # DB operations
│   │   └── sessions/            # .session files
│   │
│   ├── providers/               # 👁️ Eyes/Hands Layer
│   │   └── telethon_client.py   # Telethon wrapper
│   │
│   ├── services/                # ⚡ Nerves Layer
│   │   ├── singleton.py         # Global RepostService
│   │   ├── repost_engine.py     # Main orchestrator
│   │   ├── pair_id_healer.py    # Auto-resolves non-numeric channel IDs
│   │   ├── engine_loops.py      # Backfill, schedule flush
│   │   ├── engine_utils.py      # Classifier, dedup
│   │   ├── autonomic.py         # Heartbeat monitor
│   │   ├── session_manager.py   # Session validation
│   │   ├── stats_service.py     # Progress calculations
│   │   ├── media_cache.py       # File_id caching
│   │   └── inventory_monitor.py # Hourly alerts
│   │
│   └── utils/                   # 🔧 Utilities
│       ├── log_buffer.py        # Circular log buffer
│       └── protection.py        # AntiBanGuard
│
├── infrastructure/              # System-level checks
│   └── checks/
│       ├── guardian.py          # Pre-boot integrity
│       ├── benchmark_engine.py  # Performance testing
│       └── ui_integrity_audit.py# Routing collision
│
├── scripts/                     # Utility scripts
│   ├── simulate_stats.py        # ETA calculator
│   ├── verify_routing.py        # Routing auditor
│   └── verify_triage.py         # Classification tests
│
├── migrations/                  # Alembic migrations
├── scratch/                     # Temp storage
│   ├── temp_media/              # Downloaded media
│   └── temp_thumbs/             # Thumbnails
├── logs/                        # Application logs
└── userguide/                   # User documentation
```

---

## 🗄️ Database Schema

### Entity Relationship

```
users
    └─< repost_pairs
```

### `users` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (Telegram user ID) |
| `username` | TEXT | Telegram username |
| `session_string` | TEXT | Telethon session (encrypted) |
| `has_active_session` | BOOLEAN | Session validity |
| `is_admin` | BOOLEAN | Admin privileges |
| `is_premium` | BOOLEAN | Premium access |
| `premium_until` | DATETIME | Premium expiry |
| `created_at` | DATETIME | Auto-set |

### `repost_pairs` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key |
| `user_id` | INTEGER | FK → users.id |
| `source_id` | TEXT | Source channel |
| `destination_id` | TEXT | Destination channel |
| `source_display` | TEXT | Cached display name |
| `destination_display` | TEXT | Cached display name |
| `filter_type` | INTEGER | 0=Keep, 1=Remove, 2=Replace, 3=Nuke |
| `replacement_link` | TEXT | Replacement text |
| `schedule_interval` | INTEGER | Minutes between posts |
| `start_from_msg_id` | INTEGER | Backfill starting point |
| `total_posts_source` | INTEGER | Cached message count |
| `is_active` | BOOLEAN | Running status |
| `status` | TEXT | normal / error |
| `is_protected` | BOOLEAN | Download/upload mode |
| `loop_history` | BOOLEAN | Restart when done |
| `error_count` | INTEGER | Consecutive errors |
| `consecutive_heals` | INTEGER | Healing attempts |
| `last_reposted_at` | DATETIME | Last successful post |
| `next_allowed_post_at` | DATETIME | Persistent timer |
| `alerted_3d` | BOOLEAN | 3-day alert sent |
| `alerted_caught_up` | BOOLEAN | Caught-up alert sent |

---

## 🎮 Bot Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Main menu |
| `/alertbot` | Verify for inventory alerts |

### Main Menu Options

| Button | Action |
|--------|--------|
| 📱 Session | Upload/manage Telethon session |
| 📢 My Pairs | View and manage repost pairs |
| ➕ New Pair | Create a new repost pair |
| 📊 Stats | View progress statistics |
| ❓ Support | Contact support |

### Pair Management

| Action | Description |
|--------|-------------|
| ▶️/⏸️ | Pause/Resume pair |
| 🔁 | Toggle loop history |
| 🔒 | Toggle protection mode |
| ⚡ | Force immediate post |
| 🗑️ | Delete pair |

### Filter Modes

| Mode | Name | Behavior |
|------|------|----------|
| 0 | Keep | Leave text unchanged |
| 1 | Remove | Strip all links and @usernames |
| 2 | Replace | Replace links with custom text |
| 3 | Nuke | Replace entire message with custom text |

### Schedule Options

| Option | Interval |
|--------|----------|
| Instant | 0 (immediate) |
| 5 minutes | 5 |
| 15 minutes | 15 |
| 30 minutes | 30 |
| 1 hour | 60 |
| 2 hours | 120 |
| 6 hours | 360 |
| 12 hours | 720 |
| 24 hours | 1440 |

---

## 🌐 REST API

### Authentication

All endpoints except `/health` require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your_api_key" http://localhost:5555/stats/123456789
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/stats/{user_id}` | Get user statistics |
| POST | `/pair` | Create a pair |
| POST | `/session` | Ingest session string |
| POST | `/pair/{pair_id}/toggle` | Toggle pair |
| DELETE | `/pair/{pair_id}` | Delete pair |
| PATCH | `/pair/{pair_id}` | Update pair |
| GET | `/pairs/all` | Admin: all pairs |
| GET | `/session/{user_id}` | Admin: get session |

### Example Requests

**Create a Pair:**
```bash
curl -X POST http://localhost:5555/pair \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123456789,
    "source_id": "@source_channel",
    "destination_id": "@dest_channel",
    "interval": 30,
    "filter_type": 1,
    "start_id": 1000
  }'
```

**Get Stats:**
```bash
curl -H "X-API-Key: your_api_key" \
  http://localhost:5555/stats/123456789
```

---

## 🔧 Core Concepts

### Backfill

Sequential reposting from an older message ID to the present. The bot fetches batches of 50 messages, processes each one, and advances a bookmark pointer.

### Sentinel Mode

After catching up to the present, the bot watches for new messages in real-time rather than backfilling.

### Protected Media

Messages with `noforward` enabled cannot be forwarded. The bot downloads them to `scratch/temp_media/`, preserves metadata (duration, dimensions, filename), and re-uploads them.

### Autonomic Healing

The heartbeat monitor runs every 15 minutes and scans for stalled pairs. If a pair hasn't posted within `threshold = interval + max(15, interval * 0.25)` minutes, it triggers a surgical heal.

### Failed Media Lock (FML)

"Landmine" messages with corrupt media are locked to prevent infinite retry loops.

### Fresh Fetch

For scheduled posts, the bot re-retrieves the message 1 second before sending to prevent stale file reference errors.

### Human Jitter

Random delays added to operations to simulate human behavior and avoid Telegram's anti-bot detection.

---

## 🚀 Deployment

### PM2 Configuration

`ecosystem.config.js`:
```javascript
module.exports = {
  apps: [{
    name: "mister-reposter",
    script: "main.py",
    interpreter: "python3",
    max_memory_restart: "250M",
    autorestart: true,
    restart_delay: 5000
  }]
}
```

### Deploy Commands

```bash
# Start
pm2 start ecosystem.config.js

# Restart
pm2 restart mister-reposter

# View logs
pm2 logs mister-reposter

# Stop
pm2 stop mister-reposter

# Monitor
pm2 monit
```

### First-Time Setup

1. Clone repository
2. Create `.env` with secrets
3. Install dependencies: `pip install -r requirements.txt`
4. Start with PM2: `pm2 start ecosystem.config.js`

---

## 🐛 Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Bot not responding | Invalid token | Check `BOT_TOKEN` in `.env` |
| Session invalid | Expired/revoked | Re-upload session via bot |
| FloodWait errors | Too many requests | Bot auto-handles; reduce interval |
| Media not sending | Stale file reference | Fresh Fetch handles automatically |
| Pair stuck | Network issue | Autonomic healing will fix |
| Double heartbeat | Bug in `__init__` | Ensure only `main.py` starts it |

### Logs

```bash
# PM2 logs
pm2 logs mister-reposter --lines 100

# Application logs
tail -f logs/app.log

# Bot log viewer
# Use the 📋 Logs button in the bot menu
```

### Health Check

```bash
curl http://localhost:5555/health
# Expected: {"status": "ok"}
```

---

## 🧩 Extending the Bot

### Adding a New Filter Mode

1. Add to `FILTER_LABELS` in `bot/keyboards.py`
2. Update `MessageCleaner.clean()` in `core/repost/logic.py`
3. Add tests in `scripts/verify_triage.py`

### Adding a New Schedule Option

1. Add to `SCHEDULE_LABELS` in `bot/keyboards.py`
2. Add callback handler in `pairs.py` (`setsched_`)
3. Ensure `schedule_interval` is stored correctly

### Adding a New API Endpoint

1. Add route to `api/routes.py`
2. Add schema to `api/schemas.py`
3. Call appropriate `repost_service` method

### Adding a New Admin Feature

1. Add handler to `bot/handlers/admin_users.py`
2. Add button to `bot/keyboards_admin.py`
3. Add callback handler in same file

---

## 📚 Glossary

| Term | Definition |
|------|------------|
| **Backfill** | Sequential reposting from older to present |
| **FloodWait** | Telegram rate limit error |
| **Ghost Message** | Deleted message (skipped) |
| **Protected Media** | `noforward` content requiring download/upload |
| **Autonomic Healing** | Self-healing that detects and fixes stalls |
| **Sentinel Mode** | Watching for new messages after catch-up |
| **Failed Media Lock** | Locks corrupt media to prevent loops |
| **Surgical Healing** | Manual force-post to unstick a loop |
| **Nuke & Replace** | Filter mode replacing entire text |
| **Fresh Fetch** | Re-retrieve before send to prevent stale refs |
| **Human Jitter** | Random delays to avoid detection |

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 📞 Support

- **Telegram:** [@MisterKayCodes](https://t.me/MisterKayCodes)
- **Issues:** [GitHub Issues](https://github.com/yourusername/Mister_ReposterV2/issues)
- **Docs:** See `userguide/` directory

---

**Built with ❤️ by MisterKayCodes**

*Last updated: 2025*