import time

TTL_SECONDS = 1500

class TokenCache:
    def __init__(self):
        self._store = {}

    def get(self, region):
        entry = self._store.get(region)
        if entry and time.time() < entry["expires_at"]:
            return entry["data"]
        return None

    def set(self, region, data):
        self._store[region] = {
            "data": data,
            "expires_at": time.time() + TTL_SECONDS,
        }
        self._cleanup()

    def invalidate(self, region):
        self._store.pop(region, None)

    def _cleanup(self):
        now = time.time()
        stale = [k for k, v in self._store.items() if v["expires_at"] < now]
        for k in stale:
            del self._store[k]


token_cache = TokenCache()
