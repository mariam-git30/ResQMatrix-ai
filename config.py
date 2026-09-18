"""Application configuration for local development and Replit."""

import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


class Config:
    """Environment-backed settings with safe development defaults."""

    SECRET_KEY = os.getenv("SECRET_KEY", "resqmatrix-development-key")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "1").lower() in {"1", "true", "yes"}
    DATABASE_PATH = os.getenv(
        "RESQMATRIX_DATABASE_PATH",
        str(PROJECT_DIR / "database" / "resqmatrix.db"),
    )