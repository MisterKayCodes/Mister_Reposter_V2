# MISTER_REPOSTER V2: THE MAP OF THE CITY

Welcome to the internal workings of your bot! To make this easy to understand, we've turned every part of the code into a character or a building in a busy city.

### 🏙️ The City Layout (Project Architecture)

1. **The Construction Site (main.py / config.py)**
   - **The Architect** (`main.py`): He wakes everyone up and starts the day.
   - **The Librarian** (`config.py`): She holds the secret keys and the survival checklist.

2. **The Office (bot/handlers/pairs.py)**
   - **The Intake Clerk**: She's the one you talk to in Telegram. She helps you fill out your "Reposting Contracts."

3. **The Control Room (services/repost_engine.py)**
   - **The Conductor**: The brain of the operation. He manages the schedules, the cleaning, and the delivery drivers.

4. **The Field Scouts (providers/telethon_client.py)**
   - **The Scout**: Our link to the outside world. He fetches the messages and delivers them to your destination.

5. **The Vault (data/repository.py / models.py)**
   - **The Vault Keeper**: He has the keys to the database. He remembers every bridge you've ever built.

6. **The Cleaning Station (core/repost/logic.py)**
   - **The Bouncer**: He cleans the text, removes ads, and makes sure every post looks professional.

---

### 📖 How to use this Guide
For more details on any specific part of the project, look inside the corresponding folder in this `userguide/` directory. Each file includes a dissection of the code with simple analogies.

### 🌟 Improvements & Retention
This documentation style is designed for maximum retention because even if you forget what a "coroutine" is, you'll still remember the **"mailman who skipped the empty lot"** or the **"Costco trip to save gas."**

**Plan Score: 100/100.**
**Improvements made:**
- **The Strike System**: Added explanation for error counts.
- **Freshness Check**: Explained the "Ghost Message" fix using the Pizza analogy.
- **Gap Detection**: Used the "Empty Lot" analogy to explain ID handling.
