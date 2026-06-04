"""
agent_platform/config.py
Environment-based configuration with validation.
Imported by every project in this monorepo.
"""

import os # built into Python, lets you read environment variables
from dataclasses import dataclass # built into Python, reduces boilerplate when creating classes
from dotenv import load_dotenv # from the python-dotenv package we installed, reads your .env file

# Runs immediately when this file is imported. Reads your .env file and loads ANTHROPIC_API_KEY into the environment so os.getenv() can find it.
load_dotenv()

@dataclass
class Config:
    anthropic_api_key: str
    default_model: str
    dev_model: str
    log_level: str
    environment: str

    @classmethod
    def from_env(cls) -> "Config":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. "
                "Add it to your .env file."
            )
        return cls(
            anthropic_api_key=api_key,
            default_model=os.getenv(
                "DEFAULT_MODEL", "claude-haiku-4-5"
            ),
            dev_model=os.getenv(
                "DEV_MODEL", "claude-haiku-4-5"
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            environment=os.getenv("ENVIRONMENT", "development"),
        )


# Module-level singleton — import this everywhere
config = Config.from_env()
