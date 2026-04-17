import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    telegram_bot_token: str
    anthropic_api_key: str
    model: str = "claude-sonnet-4-6"
    max_history: int = 20

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        return cls(telegram_bot_token=token, anthropic_api_key=api_key)

config = Config.from_env()
