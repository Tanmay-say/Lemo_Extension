import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
from core.config import REDIS_URL
# Connect to Redis
r = redis.Redis.from_url(REDIS_URL)

print(r.ping())