from dataclasses import dataclass
from datetime import datetime

@dataclass
class TwitterResult:
    channel: str
    username: str
    description: str
    published_date: datetime
    embed_url: str