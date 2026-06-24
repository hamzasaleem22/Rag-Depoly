import hashlib
import logging
from src.config import config

logger = logging.getLogger(__name__)

try:
    from diskcache import Cache as DiskCache
except ImportError:
    DiskCache = None
    logger.warning("diskcache not installed; falling back to memory-only cache")


class QueryCache:
    def __init__(self):
        self._memory: dict[str, dict] = {}
        self._disk: DiskCache | None = None
        self._enabled = config.cache.enabled
        if not self._enabled:
            return
        if config.cache.backend == "disk":
            from src.config import BASE_DIR
            self._disk = DiskCache(str(BASE_DIR / ".cache"))
        self._max_size = config.cache.max_size
        self._ttl = config.cache.ttl_seconds

    def _key(self, question: str) -> str:
        return hashlib.sha256(question.encode()).hexdigest()

    def get(self, question: str) -> dict | None:
        if not self._enabled:
            return None
        key = self._key(question)
        if config.cache.backend == "memory":
            entry = self._memory.get(key)
            if entry is None:
                return None
            self._memory[key] = {**entry, "_hits": entry.get("_hits", 0) + 1}
            return entry["result"]
        else:
            return self._disk.get(key)

    def set(self, question: str, result: dict) -> None:
        if not self._enabled:
            return
        key = self._key(question)
        entry = {"result": result, "_hits": 0}
        if config.cache.backend == "memory":
            if len(self._memory) >= self._max_size:
                lru = min(self._memory.items(), key=lambda x: x[1].get("_hits", 0))[0]
                del self._memory[lru]
            self._memory[key] = entry
        else:
            self._disk.set(key, result, expire=self._ttl)

    def clear(self) -> None:
        self._memory.clear()
        if self._disk:
            self._disk.clear()

    @property
    def size(self) -> int:
        if config.cache.backend == "memory":
            return len(self._memory)
        return len(self._disk) if self._disk else 0


cache = QueryCache()
