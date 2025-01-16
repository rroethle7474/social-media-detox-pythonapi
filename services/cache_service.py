from cachetools import TTLCache
from datetime import datetime

class CacheService:
    def __init__(self, maxsize=100, ttl=3600):  # 1 hour default TTL
        self.cache = TTLCache(maxsize=maxsize, ttl=ttl)
        self.stats = {
            'hits': 0,
            'misses': 0,
            'last_cleared': None
        }

    def get(self, key):
        value = self.cache.get(key)
        if value is not None:
            self.stats['hits'] += 1
        else:
            self.stats['misses'] += 1
        return value

    def set(self, key, value):
        self.cache[key] = value

    def has(self, key):
        return key in self.cache

    def clear(self):
        self.cache.clear()
        self.stats['last_cleared'] = datetime.utcnow()

    def remove(self, key):
        if key in self.cache:
            del self.cache[key]

    def get_stats(self):
        return {
            **self.stats,
            'current_size': len(self.cache),
            'max_size': self.cache.maxsize,
            'ttl': self.cache.ttl
        }