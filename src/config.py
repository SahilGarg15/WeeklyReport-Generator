"""
src/config.py
─────────────
Loads config.json and .env, exposes a single `cfg` dict.
All modules import `cfg` from here.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

_cfg_path = ROOT / "config.json"
if not _cfg_path.exists():
    raise FileNotFoundError(f"config.json not found at {_cfg_path}")

with _cfg_path.open(encoding="utf-8-sig") as _f:
    cfg: dict = json.load(_f)

# Inject secrets from .env (never stored in config.json)
cfg["groq_api_key"] = os.getenv("GROQ_API_KEY", "")
cfg["email"]["app_password"] = os.getenv("EMAIL_APP_PASSWORD", "")
cfg["email"]["sender"]       = os.getenv("EMAIL_SENDER",       cfg["email"].get("sender", ""))

# Resolve relative paths to absolute from project root
cfg["_root"] = ROOT
cfg["data_file"] = str(ROOT / cfg.get("data_file", "data/weekly_data.csv"))
cfg["reports_dir"] = str(ROOT / cfg.get("reports_dir", "reports"))
