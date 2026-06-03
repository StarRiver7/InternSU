"""模式缓存 - 基于 TTL 的模式缓存，避免重复的 MySQL 查询。"""
import time
from app.core.logger import get_logger
logger = get_logger(__name__)
SCHEMA_CACHE_TTL = 300

class SchemaCache:
    def __init__(self):
        self._cache = None
        self._ts = 0.0
        self._context_str = ""
    def is_valid(self):
        return self._cache is not None and (time.time() - self._ts) < SCHEMA_CACHE_TTL
    def get(self):
        return self._cache if self.is_valid() else None
    def set(self, data):
        self._cache = data; self._ts = time.time()
    def get_context(self):
        return self._context_str if self.is_valid() and self._context_str else None
    def set_context(self, ctx):
        self._context_str = ctx
    def invalidate(self):
        self._cache = None; self._ts = 0.0; self._context_str = ""

schema_cache = SchemaCache()
