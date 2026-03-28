import json
from redis.asyncio import Redis


class EventBus:
    def __init__(self, redis: Redis, max_length: int = 100_000):
        self.redis = redis
        self.max_length = max_length

    async def publish(self, stream: str, data: dict) -> str:
        entry = {k: json.dumps(v) if not isinstance(v, str) else v for k, v in data.items()}
        approximate = self.max_length > 1000
        msg_id = await self.redis.xadd(
            f"algomatter:{stream}", entry, maxlen=self.max_length, approximate=approximate
        )
        return msg_id

    async def read_recent(self, stream: str, count: int = 10) -> list[dict]:
        messages = await self.redis.xrevrange(f"algomatter:{stream}", count=count)
        results = []
        for msg_id, data in messages:
            parsed = {}
            for k, v in data.items():
                key = k.decode() if isinstance(k, bytes) else k
                val = v.decode() if isinstance(v, bytes) else v
                try:
                    parsed[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    parsed[key] = val
            results.append(parsed)
        return results
