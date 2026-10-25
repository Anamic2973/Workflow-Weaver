"""
Centralized configuration loaded from environment variables.
All secrets are read at runtime — nothing is hardcoded or committed.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # LLM
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    # Notion MCP
    NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
    NOTION_PAGE_ID: str = os.getenv("NOTION_PAGE_ID", "")

    # Google Drive MCP
    GOOGLE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    GOOGLE_DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    # Microsoft Teams
    TEAMS_WEBHOOK_URL: str = os.getenv("TEAMS_WEBHOOK_URL", "")

    # Langfuse
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # App
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BASE_DELAY_SECONDS: float = float(os.getenv("RETRY_BASE_DELAY_SECONDS", "1.0"))
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")


settings = Settings()
