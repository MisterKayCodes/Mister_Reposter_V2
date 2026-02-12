# MISTER — A Developer’s Journal

*Written a few days after the MVP, when the adrenaline wore off and reality stayed.*

I didn’t start this as documentation.  
I started it because if I didn’t write it down, I’d forget how hard this actually was.

This is not a spec.  
It’s not a tutorial.  
It’s a memory anchor — for the days when the code works and I forget the cost, and for the days when it breaks and I forget the progress.

---

## Phase 0 — Empty Folder, Loud Confidence

It began the way most bad decisions do: an empty folder and confidence that hadn’t earned its place yet.

I created directories like someone who wanted to look serious — `/bot`, `/services`, `/data`, `/core`.  
Skeleton files everywhere.  
A virtual environment.  
Git initialized.

It looked like a real project long before it behaved like one.

The first warning sign came early.  
aiogram and aiofiles refused to install together. No explanation. Just silent disagreement.

Hours later, I learned the truth:  
dependencies have opinions, and they do not care about your timeline.

Bumping the aiofiles version fixed it.  
Lesson one arrived quietly:  
**software isn’t hostile, it’s indifferent.**

---

## Phase 1 — Teaching the Bot to Remember

I thought reposting would be the hard part.

I was wrong.

The real problem was memory.

The bot would ask a user for a session… then immediately forget it asked.  
Five seconds later, it was confused again. Like it had no object permanence.

That’s when FSM entered the picture.

States. Transitions. Waiting rooms for user intent.

Painful to wire. Easy to get wrong.  
But once it worked, something shifted.

The bot stopped feeling like a script and started feeling like a thing that stayed aware between moments.

That was the first time it felt alive.

---

## The Vault — When Nothing Was Actually Saved

I built the database models carefully.  
Users. Repost pairs. Relationships that made sense on paper.

Then I ran the bot.

No database file.

Nothing on disk.

Turns out I never called `init_db()`.

One missing function call erased the entire illusion of persistence.

When I fixed it, everything changed.  
Data survived restarts.  
State outlived processes.

That’s when I learned the difference between *working code* and *real systems*.

Persistence is the line.

---

## The Eyes — Telethon and the Art of Not Blocking Everything

Telethon didn’t misbehave.  
I misused it.

`run_until_disconnected()` froze the entire organism.  
The bot could see messages but couldn’t respond to anything else.

It was watching, but not breathing.

Switching to `asyncio.create_task()` fixed it.  
Listeners ran in the background.  
The Mouth could talk again while the Eyes stayed open.

That moment mattered more than I expected.

This wasn’t a script anymore.  
It was concurrent.  
Alive in parallel.

---

## Boundaries — When “Convenient” Turned Into “Wrong”

At some point, I let services talk directly to the database.

It felt efficient.  
It felt fast.

It was wrong.

The bugs that followed weren’t loud — they were subtle, systemic, and exhausting.

Once I enforced boundaries, things calmed down:

- Core decides rules.
- Services orchestrate.
- Repositories touch data.
- Providers talk to the outside world.

Nothing magical happened.  
But the headaches reduced.

That’s when I learned:  
**most complexity comes from blurred responsibility, not advanced logic.**

---

## Resurrection — Teaching the Bot to Survive Death

The bot reposted messages.

Then I restarted it.

Silence.

All listeners were gone.

The system had no memory of what it was watching because session paths were never saved. Recovery had nothing to resurrect.

Fixing that felt less like coding and more like giving the system a spine.

Once recovery worked, I trusted it more.  
Not because it was perfect — but because it remembered itself.

That’s infrastructure.

---

## Bugs That Didn’t Feel Like Bugs

Some failures weren’t errors. They were moods.

Background tasks crashing silently.  
SQLite locking itself out of spite.  
Commands treated like channel IDs.  
Config types lying about who they were.  
Network timeouts freezing everything while pretending all was well.

Each one drained patience.

Each one taught restraint.

By the end, I wasn’t fixing bugs — I was designing guardrails.

---

## The First Message

When the first live repost landed, I didn’t celebrate.

I just sat there.

That message wasn’t impressive.  
But it proved the entire chain worked:

User input → session → database → listener → logic → repost engine → destination.

That was the moment this stopped being a toy.

---

## Stability — The Unsexy Work

After the win came the grind.

Filtering commands.  
Pooling connections.  
Adding timeouts.  
Cleaning corrupted state.

Nothing glamorous.  
Everything necessary.

Trust isn’t built at peak moments.  
It’s built in boredom.

---

## Phase 2 — When Life Started Interrupting

This phase didn’t start clean.

I was hungry.  
The AC was too cold.  
I hadn’t showered in a full day.  
Coco by Gabzy was on repeat, and nothing was sticking.

The bot suddenly forgot where its `data` directory lived.

I cooked pepper soup.  
Bought new WiFi because the old one ran out mid-debug.  
Ate hot beans and questioned every life choice.

Listened to *I Wish* by 21 Savage and wished the code would just work already.

I was angry. Quietly.

---

### Media Support — Teaching the Eyes to See More

Text was no longer enough.

I rewired the repost engine to stop assuming messages were words.

Media moved through RAM now.  
Photos. Videos. Documents.

No temp files.  
No cleanup rituals.

The organism learned to carry weight, not just speech.

---

### The Gatekeeper — When Protection Blocks the Owner

Middleware arrived with good intentions.

It blocked everyone.  
Including valid users.

SQLite lagged.  
Reality moved faster than commits.

The fix was simple and humbling:

Trust disk state as much as database state.

If the session file exists, access is granted.

Security should protect flow, not suffocate it.

---

### The Librarian Learns to Write

The repository couldn’t save session strings.

It had shelves but no pen.

Adding `update_session_string` and forcing explicit commits fixed it.

Data finally stayed where it was put.

---

## Life Bleeding Into Code

Somewhere between bugs:

- I realized I live alone.  
  A gift and a curse.

- I can’t finish a full FC game without thinking about logic pipelines.

- Drake lyrics hit different if you’re rich. Otherwise, they’re just theory.

- I wonder if I’ll ever be a senior dev — and if I even want to work for anyone.

- Burna Boy unlocked my thinking again after I finally showered.

- I did my daily pushups.  
  Not because I was motivated.  
  Because routine is sometimes the only anchor.

---

## Where Things Stand

The system holds.

Media logic exists.  
Middleware behaves.  
Paths align.

Remaining work is verification — not expansion.

Stability before ambition.

I stopped to eat before frustration wrote bugs faster than code.

That was the right call.

---

## Closing Thought

This bot isn’t impressive because it reposts messages.

It’s impressive because it survives confusion, restarts, hunger, bad music moods, and tired thinking.

Software doesn’t fail when logic is wrong.

It fails when humans push through exhaustion instead of stepping back.

Tomorrow, I’ll read this before touching the code again.
