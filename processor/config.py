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

# --- LLM (price + title + description) ---
# 走 Anthropic Messages 接口。默认用官方 Claude；也可指向任何 Anthropic 兼容
# 端点，比如 Moonshot/Kimi：把 LLM_BASE_URL 设为 https://api.moonshot.ai/anthropic、
# 模型设为 kimi-k2.5、key 填你的 Moonshot key 即可。
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
# 兼容旧名：优先 LLM_BASE_URL，其次 ANTHROPIC_BASE_URL；都没有就用官方地址。
LLM_BASE_URL = _get("LLM_BASE_URL") or _get("ANTHROPIC_BASE_URL")
CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-sonnet-4-6")

# --- Frame extraction ---
FRAMES_PER_ITEM = int(_get("FRAMES_PER_ITEM", "5"))
SAMPLE_FPS = float(_get("SAMPLE_FPS", "2"))  # candidate frames sampled per second

# --- Magic word(s) that separate items ---
TRIGGERS = [t.strip() for t in _get("TRIGGERS", "").split(",") if t.strip()] or None

# --- 市场价联网搜索（Moonshot/Kimi 的 $web_search，走 OpenAI 兼容接口）---
# 录视频时对某件说出 PRICE_TRIGGERS 里的暗号，才会去联网查它的新品参考价。
PRICE_TRIGGERS = [
    t.strip() for t in _get("PRICE_TRIGGERS", "查原价").split(",") if t.strip()
]
SEARCH_BASE_URL = _get("SEARCH_BASE_URL", "https://api.moonshot.ai/v1")
SEARCH_MODEL = _get("SEARCH_MODEL", "kimi-k2.5")
# 搜索用的 key，默认复用上面的 key（Moonshot 同一把 key 两个接口都能用）。
SEARCH_API_KEY = _get("SEARCH_API_KEY") or ANTHROPIC_API_KEY

# --- Listing defaults ---
CONTACT = _get("CONTACT", "")  # your WeChat id, written into every listing
CURRENCY = _get("CURRENCY", "USD")

# --- WeChat 云开发 (only needed by publish.py) ---
WX_APPID = _get("WX_APPID")
WX_APPSECRET = _get("WX_APPSECRET")
WX_ENV_ID = _get("WX_ENV_ID")
PRODUCTS_COLLECTION = _get("PRODUCTS_COLLECTION", "products")
