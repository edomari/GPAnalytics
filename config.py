"""
Centralized application configuration.

All the "magic" values scattered throughout the original code (base URLs, valid year ranges,
HTTP timeouts) live here in a single place, and can be overridden via environment variables.
This allows for different configurations for development/staging/production without touching
the source code.
"""
import os

class Config:

    API_BASE_URL = "https://api.motogp.pulselive.com/motogp/v1"
    API_ENTRIES_URL = "https://api.motogp.pulselive.com/motogp/v2/results/entries"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", 10))
    HTTP_MAX_RETRIES = int(os.environ.get("HTTP_MAX_RETRIES", 2))

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

config = Config()