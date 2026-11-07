# Mister Reposter V2 Lessons Learned

Format:
## [Short Title]
- **Date**: YYYY-MM-DD
- **Problem**: What broke or was needed
- **Root Cause**: Why it happened
- **Fix**: What was done
- **Verified by**: Exact observation from user/logs

## Telegram Stars Paywall Implementation & Telethon Layer Pinning
- **Date**: 2026-11-06
- **Problem**: Adding Stars paywalls broke at import, had multiple paywall leaks across albums/protected media, and test posts appeared unlocked to admins.
- **Root Cause**: Telethon 1.36.0 lacked Layer 187+ InputMediaPaidMedia; fail-closed exception handling was missing; channel admins automatically bypass client-side Stars prompts.
- **Fix**: Upgraded Telethon to >=1.41,<2; added StarsLockFailed fail-closed guards in telethon_client; decoupled worker niches from usernames into worker_niche DB column; verified locking using non-admin subscriber account.
- **Verified by**: Non-admin account confirmed the 11-min video (Msg 733) displayed the 50 Stars paywall prompt in Sandbox channel.

## Stars Cadence Drift on Sequential Message IDs
- **Date**: 2026-11-07
- **Problem**: Stars cadence locking (1 in 4 videos) skipped or locked consecutive posts unpredictably.
- **Root Cause**: Cadence checked `msg.id % cadence == 0`. Deleted posts or multi-item albums create non-sequential message ID gaps, breaking modulo predictability.
- **Fix**: Replaced raw `msg.id` modulo with an in-memory sequential post counter per pair.
- **Verified by**: Preview script confirmed exact deterministic 1-in-4 locking pattern across consecutive messages.

## Rotating Dynamic Captions for Audience Desensitization
- **Date**: 2026-11-07
- **Problem**: Static caption replacements lead to banner blindness over repeated posts.
- **Root Cause**: Filter Mode 3 only accepted a single static string.
- **Fix**: Upgraded `MessageCleaner` to parse multiple templates split by `---` or JSON array, randomly selecting one per dispatch.
- **Verified by**: User manually created The Red Room pair in bot UI using the new caption template flow and confirmed successful setup.

## Channel Migration Duration Sorter
- **Date**: 2026-11-07
- **Problem**: Sourcing hundreds of videos into separate VIP (<6m) and VVIP (6m+) tiers manually is error-prone and risks FloodWait bans.
- **Root Cause**: No automated duration-based sorter utility existed in the ecosystem.
- **Fix**: Built `scripts/migrate_sorter.py` with 3.5s-7s jitter, checkpointing, and live Telegram dashboard integration via `/migration`.
- **Verified by**: User confirmed videos forwarded cleanly into VIP (The Velvet Vault) and VVIP (Obsidian Black Room) channels in real time.
