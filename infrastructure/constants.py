"""
INFRASTRUCTURE: CONSTANTS
Central source of truth for the Hive's configurable parameters.
Enables "Config-Driven Development" for UI and Services.
"""

# X-Hunt Configuration
XHUNT_INTERVALS = [
    {"label": "⚡ Real-Time (Immediate)", "value": 0},
    {"label": "15 Minutes", "value": 0.25},
    {"label": "30 Minutes", "value": 0.5},
    {"label": "1 Hour", "value": 1},
    {"label": "2 Hours", "value": 2},
    {"label": "4 Hours", "value": 4},
    {"label": "8 Hours", "value": 8},
    {"label": "12 Hours", "value": 12},
    {"label": "24 Hours (Recommended)", "value": 24},
    {"label": "48 Hours", "value": 48}
]

XHUNT_FILTERS = [
    {"label": "Mode 0: As-Is (No Cleaning)", "value": 0},
    {"label": "Mode 1: Native (Strip Handles/Links)", "value": 1},
    {"label": "Mode 2: Replacement (Custom Link)", "value": 2}
]

# Architecture Inspector Defaults
# (In the future, these can be fetched from a remote config server)
MAX_FILE_LINES = 600
MAX_NESTING_DEPTH = 6
