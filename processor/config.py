"""Configuration loaded from environment / a local .env file.

Copy .env.example to .env and fill it in. Nothing here is committed.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
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
WHISPER_MODEL = _get("WHISPER_MODEL", "small")
WHISPER_LANGUAGE = _get("WHISPER_LANGUAGE", "zh")
WHISPER_DEVICE = _get("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = _get("WHISPER_COMPUTE_TYPE")

# --- Claude (price + title + description) ---
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-sonnet-4-6")

# --- Frame extraction ---
FRAMES_PER_ITEM = int(_get("FRAMES_PER_ITEM", "5"))
SAMPLE_FPS = float(_get("SAMPLE_FPS", "2"))

# --- Magic word(s) that separate items ---
TRIGGERS = [t.strip() for t in _get("TRIGGERS", "").split(",") if t.strip()] or None

# --- Defaults written into listings ---
CONTACT = _get("CONTACT", "")  # WeChat id stamped into each listing's "contact"
CURRENCY_SYMBOL = _get("CURRENCY_SYMBOL", "$")

# --- Web server (server.py) ---
JOBS_DIR = _get("JOBS_DIR", "jobs")
SERVER_HOST = _get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(_get("SERVER_PORT", "8000"))
# Shared secret added to every request from the phone. Pick something long.
SERVER_TOKEN = _get("SERVER_TOKEN", "")
# Public base URL the phone uses, e.g. http://mymac.local:8000
# Embedded in image URLs that the Shortcut fetches, so it must be reachable.
PUBLIC_BASE_URL = _get("PUBLIC_BASE_URL", "")

# Name of the iOS Shortcut that saves images to Photos. The web buttons link to
# `shortcuts://run-shortcut?name=<this>`, so it has to match exactly.
SAVE_SHORTCUT_NAME = _get("SAVE_SHORTCUT_NAME", "保存闲置图")

# --- Poster rendering ---
# Pillow can't render Chinese without a CJK font. We try these in order.
POSTER_FONT = _get(
    "POSTER_FONT",
    ":".join(
        [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    ),
)
