"""
CORE: STRATEGY PRESETS
Pre-configured automation pacing and Telegram Stars paywall pricing rules.
"""
from typing import TypedDict


class PresetConfig(TypedDict):
    name: str
    interval: int
    stars_short: int
    stars_long: int
    cadence: int
    description: str


PRESETS: dict[str, PresetConfig] = {
    "growth": {
        "name": "🚀 Aggressive Growth",
        "interval": 120,
        "stars_short": 10,
        "stars_long": 35,
        "cadence": 5,
        "description": "High volume, low friction stars paywall to maximize subscriber funnel."
    },
    "monetization": {
        "name": "💰 Monetization Beast",
        "interval": 240,
        "stars_short": 15,
        "stars_long": 50,
        "cadence": 4,
        "description": "Balanced drip interval with optimized stars pricing for consistent revenue."
    },
    "vip": {
        "name": "👑 Exclusive VIP Drip",
        "interval": 360,
        "stars_short": 25,
        "stars_long": 75,
        "cadence": 2,
        "description": "Premium slow drip, high stars barrier for elite exclusive content."
    }
}
