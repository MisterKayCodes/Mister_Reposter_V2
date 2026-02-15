"""
UTILS: LOG BUFFER
Circular buffer handler for Python's logging system.
Stores the last N log records in memory for display via the bot's Logs button.
"""
import logging
from collections import deque


class BufferedLogHandler(logging.Handler):
    def __init__(self, capacity: int = 50):
        super().__init__()
        self.buffer = deque(maxlen=capacity)
        self.formatter = logging.Formatter(
            "%(asctime)s  %(levelname)-5s  %(name)s\n  %(message)s",
            datefmt="%H:%M:%S"
        )

    def emit(self, record):
        try:
            msg = self.format(record)
            self.buffer.append(msg)
        except Exception:
            self.handleError(record)

    def get_logs(self, count: int = 25) -> str:
        entries = list(self.buffer)[-count:]
        if not entries:
            return "No logs yet."
        return "\n\n".join(entries)

    def clear(self):
        self.buffer.clear()


log_buffer = BufferedLogHandler(capacity=100)
