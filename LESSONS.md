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
