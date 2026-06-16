import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level up from this file)
load_dotenv(Path(__file__).parent.parent / ".env")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "50000"))
