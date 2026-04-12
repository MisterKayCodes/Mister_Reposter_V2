"""
SERVICES: MEDIA CACHE
Caches media references for scheduled reposts to prevent stale file references.
Stores lightweight metadata keyed by pair_id to ensure reliable delayed sends.
Also caches Telegram file_id mappings for media reuse without reuploading.
"""
import logging
import time

logger = logging.getLogger(__name__)


class MediaCache:
    def __init__(self, max_age_hours: int = 24):
        self._cache = {}
        self._max_age = max_age_hours * 3600
        self._file_id_map = {}
        self._file_id_max_age = 86400 * 7

    def cache_bundle(self, pair_id: int, messages) -> list:
        if pair_id not in self._cache:
            self._cache[pair_id] = []

        bundle = {
            "messages": messages,
            "cached_at": time.time(),
        }
        self._cache[pair_id].append(bundle)
        self._evict_stale(pair_id)
        return messages

    def get_cached(self, pair_id: int) -> list:
        self._evict_stale(pair_id)
        bundles = self._cache.get(pair_id, [])
        return [b["messages"] for b in bundles]

    def clear_pair(self, pair_id: int):
        self._cache.pop(pair_id, None)

    def clear_all(self):
        self._cache.clear()

    def store_file_id(self, original_key: str, file_id: str):
        self._file_id_map[original_key] = {
            "file_id": file_id,
            "cached_at": time.time(),
        }

    def get_file_id(self, original_key: str) -> str | None:
        entry = self._file_id_map.get(original_key)
        if not entry:
            return None
        if time.time() - entry["cached_at"] > self._file_id_max_age:
            del self._file_id_map[original_key]
            return None
        return entry["file_id"]

    def extract_media_key(self, media) -> str | None:
        if not media:
            return None
        if hasattr(media, "photo") and media.photo:
            return f"photo:{media.photo.id}"
        if hasattr(media, "document") and media.document:
            return f"doc:{media.document.id}"
        return None

    def _evict_stale(self, pair_id: int):
        if pair_id not in self._cache:
            return
        now = time.time()
        before = len(self._cache[pair_id])
        self._cache[pair_id] = [
            b for b in self._cache[pair_id]
            if (now - b["cached_at"]) < self._max_age
        ]
        evicted = before - len(self._cache[pair_id])
        if evicted > 0:
            logger.info(f"Evicted {evicted} stale cache entries for Pair #{pair_id}")
