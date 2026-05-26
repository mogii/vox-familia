"""Configuration loaded from environment / a local .env file.

Copy .env.example to .env and fill it in. Nothing here is committed.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; real env vars still work.
    pass


def _get(name, default=None):
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def require(name):
    val = _get(name)
    if not val:
        raise SystemExit(
            f"缺少配置 {name}。请在 processor/.env 里填上（参考 .env.example）。"
        )
    return val


# --- Whisper (local speech-to-text) ---
WHISPER_MODEL = _get("WHISPER_MODEL", "small")  # tiny/base/small/medium/large-v3
WHISPER_LANGUAGE = _get("WHISPER_LANGUAGE", "zh")
WHISPER_DEVICE = _get("WHISPER_DEVICE", "auto")  # auto/cpu/cuda
WHISPER_COMPUTE_TYPE = _get("WHISPER_COMPUTE_TYPE")  # e.g. int8, float16

# --- Claude (price + title + description) ---
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-sonnet-4-6")

# --- Frame extraction ---
FRAMES_PER_ITEM = int(_get("FRAMES_PER_ITEM", "5"))
SAMPLE_FPS = float(_get("SAMPLE_FPS", "2"))  # candidate frames sampled per second

# --- Magic word(s) that separate items ---
TRIGGERS = [t.strip() for t in _get("TRIGGERS", "").split(",") if t.strip()] or None

# --- Listing defaults ---
CONTACT = _get("CONTACT", "")  # your WeChat id, written into every listing
CURRENCY = _get("CURRENCY", "USD")

# --- WeChat 云开发 (only needed by publish.py) ---
WX_APPID = _get("WX_APPID")
WX_APPSECRET = _get("WX_APPSECRET")
WX_ENV_ID = _get("WX_ENV_ID")
PRODUCTS_COLLECTION = _get("PRODUCTS_COLLECTION", "products")
