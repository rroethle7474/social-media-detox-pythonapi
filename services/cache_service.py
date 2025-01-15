from cachetools import TTLCache

class CacheService:
    def __init__(self):
        self.cache = TTLCache(maxsize=100, ttl=3600)  # 3600 seconds = 1 hour

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value

    def has(self, key):
        return key in self.cache

    def clear(self):
        self.cache.clear()

    def remove(self, key):
        if key in self.cache:
            del self.cache[key]