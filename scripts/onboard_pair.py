"""
onboard_pair.py — Mister Reposter V2 Pair Onboarding Script
============================================================
Reusable, zero-hardcoding script to onboard any new repost pair
into the reposter database via the REST API.

Usage:
    py scripts/onboard_pair.py

The script will prompt for all required fields interactively,
validate the preflight checklist, and register the pair.

Preflight Checklist (enforced before any API call):
  1. Worker Telethon session exists in DB (worker_id known)
  2. Destination channel created and owner (Cristian) is admin
  3. Worker account is a MEMBER of both source and destination channels
  4. Worker niche is set correctly in DB (worker_niche column)
  5. API_KEY is available (from .env or env var REPOSTER_API_KEY)
  6. REPOSTER_API_URL is reachable

Author: Kaycris / Antigravity
"""

import os
import sys
import json
import httpx
import getpass
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Config — read from env or prompt
# ─────────────────────────────────────────────────────────────────────────────

REPOSTER_API_URL = os.getenv("REPOSTER_API_URL", "http://67.211.221.40:5555")
REPOSTER_API_KEY = os.getenv("REPOSTER_API_KEY", "")

# ─────────────────────────────────────────────────────────────────────────────
# Preflight checklist
# ─────────────────────────────────────────────────────────────────────────────

PREFLIGHT_RULES = [
    "✅  Worker Telethon session string exists in the reposter DB",
    "✅  Destination channel created — Cristian (@Cristiankk001) is admin/owner",
    "✅  Worker account is a MEMBER (not banned) in the SOURCE channel",
    "✅  Worker account is a MEMBER (not banned) in the DESTINATION channel",
    "✅  worker_niche is set correctly for this worker in the users table",
    "✅  Pair preset selected (see PRESETS below)",
    "✅  Stars pricing tier decided (Free / Cadence 15⭐ / Premium 50⭐)",
]

PRESETS = {
    "1": ("Monetization Beast",   "Stars paywall ON — 15⭐ cadence / 50⭐ premium. Max revenue mode."),
    "2": ("Growth Engine",        "Stars OFF — Strip links. Build audience fast."),
    "3": ("Relationship Builder", "Stars OFF — Keep original captions. Trust-building mode."),
    "4": ("Custom",               "You supply all params manually."),
}

SCHEDULE_OPTIONS = {
    "1": 1,
    "5": 5,
    "15": 15,
    "30": 30,
    "60": 60,
    "120": 120,
    "240": 240,
    "480": 480,
    "720": 720,
    "1440": 1440,
}

FILTER_OPTIONS = {
    "0": "Keep original",
    "1": "Strip all links",
    "2": "Replace links with custom URL",
    "3": "Nuke caption + replace",
}


def hr(char="─", width=60):
    print(char * width)


def prompt(label, default=None):
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"  {label}{suffix}: ").strip()
    return val if val else default


def confirm(msg):
    return input(f"\n  {msg} (y/n): ").strip().lower() == "y"


def run_preflight():
    hr("═")
    print("  🚀 MISTER REPOSTER — PAIR ONBOARDING PREFLIGHT")
    hr("═")
    print("\n  Complete ALL checks before continuing.\n")
    for rule in PREFLIGHT_RULES:
        print(f"    {rule}")
    print()
    if not confirm("Have you completed ALL preflight checks above?"):
        print("\n  ❌ Aborting. Complete the checklist first.\n")
        sys.exit(1)
    print("  ✅ Preflight confirmed.\n")


def select_preset():
    hr()
    print("  📦 SELECT PRESET\n")
    for k, (name, desc) in PRESETS.items():
        print(f"    [{k}] {name} — {desc}")
    print()
    choice = prompt("Preset number", "1")
    if choice not in PRESETS:
        print("  Invalid preset. Defaulting to 1.")
        choice = "1"
    name, desc = PRESETS[choice]
    print(f"\n  Selected: {name}\n")
    return choice, name


def collect_pair_params(preset_choice):
    hr()
    print("  📋 PAIR PARAMETERS\n")

    source_id     = prompt("Source channel ID (e.g. -1004371076737)")
    dest_id       = prompt("Destination channel ID (e.g. -1004389472032)")
    worker_id     = prompt("Worker Telegram user ID (e.g. 8943238124)")
    niche         = prompt("Niche tag (e.g. nsfw)", "nsfw")

    hr()
    print("  ⏰ SCHEDULE\n")
    for k, v in SCHEDULE_OPTIONS.items():
        print(f"    {k}m")
    interval_min  = prompt("Interval in minutes", "240")
    if interval_min not in [str(k) for k in SCHEDULE_OPTIONS.keys()]:
        print(f"  Custom interval: {interval_min}m")

    hr()
    print("  🧹 FILTER TYPE\n")
    for k, v in FILTER_OPTIONS.items():
        print(f"    [{k}] {v}")
    filter_type   = prompt("Filter type", "1")

    stars_enabled = False
    stars_price   = 0
    if preset_choice == "1":
        stars_enabled = True
        stars_price = int(prompt("Default Stars price for unlocked videos (0 = auto-tier)", "0"))

    start_from    = prompt("Start from message ID (0 = latest)", "0")
    pair_label    = prompt("Pair label / description (for your reference)")

    return {
        "source_channel_id":      int(source_id),
        "destination_channel_id": int(dest_id),
        "assigned_user_id":       int(worker_id),
        "niche":                  niche,
        "interval_minutes":       int(interval_min),
        "filter_type":            int(filter_type),
        "stars_enabled":          stars_enabled,
        "stars_price":            stars_price,
        "start_from_msg_id":      int(start_from),
        "label":                  pair_label or "Unnamed Pair",
    }


def call_api(params, api_key, api_url):
    hr()
    print("  📡 REGISTERING PAIR VIA API...\n")
    url = f"{api_url}/pairs/create"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    try:
        resp = httpx.post(url, json=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        print(f"  ✅ Pair registered! Pair ID: {data.get('pair_id', 'N/A')}")
        print(f"  Response: {json.dumps(data, indent=4)}")
        return data
    except httpx.HTTPStatusError as e:
        print(f"  ❌ API error {e.response.status_code}: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        sys.exit(1)


def print_fleet_entry(params, preset_name):
    hr()
    print("  📖 FLEET REGISTRY ENTRY — copy this into C:\\Kaycris\\DOCS\\FLEET_REGISTRY.md\n")
    print(f"""  | **New Pair** | Pair Label: {params['label']} | — | — | — |
  - Source:      {params['source_channel_id']}
  - Destination: {params['destination_channel_id']}
  - Worker ID:   {params['assigned_user_id']}
  - Niche:       {params['niche']}
  - Preset:      {preset_name}
  - Interval:    {params['interval_minutes']}m
  - Filter:      {params['filter_type']}
  - Stars:       {'ON' if params['stars_enabled'] else 'OFF'}
""")


def main():
    global REPOSTER_API_KEY

    print()
    hr("═")
    print("  MISTER REPOSTER V2 — PAIR ONBOARDING WIZARD")
    hr("═")

    # API key
    if not REPOSTER_API_KEY:
        REPOSTER_API_KEY = getpass.getpass("  Enter REPOSTER_API_KEY: ").strip()
    if not REPOSTER_API_KEY:
        print("  ❌ No API key provided. Set REPOSTER_API_KEY env var or enter it above.")
        sys.exit(1)

    # Preflight
    run_preflight()

    # Preset selection
    preset_choice, preset_name = select_preset()

    # Collect params
    params = collect_pair_params(preset_choice)

    # Confirm before submit
    hr()
    print("  📝 SUMMARY\n")
    for k, v in params.items():
        print(f"    {k}: {v}")
    print()
    if not confirm("Submit this pair to the reposter?"):
        print("\n  Cancelled.\n")
        sys.exit(0)

    # API call
    call_api(params, REPOSTER_API_KEY, REPOSTER_API_URL)

    # Fleet entry hint
    print_fleet_entry(params, preset_name)

    hr("═")
    print("  🎉 DONE. Pair is live. Monitor via PM2 logs on the VPS.\n")
    hr("═")


if __name__ == "__main__":
    main()
