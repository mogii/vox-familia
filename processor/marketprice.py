"""Look up a product's current retail/reference price via Moonshot's web search.

Uses Kimi's built-in $web_search tool over the OpenAI-compatible endpoint
(api.moonshot.ai/v1). Two stages, both on the same endpoint/key:
  1. a search-enabled chat that researches the price and cites a source;
  2. a plain JSON-mode call that distills that answer into a clean record.

Only called for items where the seller spoke the price-lookup magic word.
"""

import json
import warnings

import config

# 我们把含 builtin_function 工具调用的 assistant 消息回传给接口，openai SDK 的
# pydantic 模型不认识这个类型、会发一条无害的序列化告警。请求本身是成功的，静音即可。
warnings.filterwarnings(
    "ignore", message="Pydantic serializer warnings", category=UserWarning
)

# Whether the price-lookup magic word appears in an item's transcript.
from segment import _normalize  # reuse the same punctuation-insensitive matcher


def wants_lookup(transcript, triggers=None):
    triggers = triggers or config.PRICE_TRIGGERS
    norm = _normalize(transcript)
    return any(_normalize(t) in norm for t in triggers)


SEARCH_SYSTEM = (
    "你是帮卖家整理二手宝宝用品的助手。卖家会口述一件商品（可能含品牌、型号、年份），"
    "请联网搜索它【当前全新/零售】的大致售价，作为二手定价的参考。优先美国市场、美元。"
    "只看新品或全新在售价格。给出一个代表性价格或区间，并附上你参考的来源链接。"
    "如果搜索后找不到可靠对应的商品价格，请明确说『没有找到可靠价格』，不要编。"
)

EXTRACT_SYSTEM = (
    "把下面这段关于商品价格的说明整理成 JSON，字段："
    "found(布尔，是否找到可靠的新品参考价)、"
    "price(数字，代表性美元价格；区间就取中间值；没找到填 null)、"
    "price_text(字符串，给人看的价格，如 \"$89.99\" 或 \"$40–60\"；没找到填空串)、"
    "source(字符串，最相关的来源链接；没有填空串)。只输出 JSON。"
)

WEB_SEARCH_TOOL = [{"type": "builtin_function", "function": {"name": "$web_search"}}]


def _client():
    from openai import OpenAI

    return OpenAI(api_key=config.SEARCH_API_KEY, base_url=config.SEARCH_BASE_URL)


def _research(client, transcript):
    """Run the $web_search loop; return the model's final natural-language answer."""
    messages = [
        {"role": "system", "content": SEARCH_SYSTEM},
        {"role": "user", "content": f"卖家口述：{transcript}\n请查它的新品参考价。"},
    ]
    # Kimi may fire $web_search several times; echo each call's args back so it
    # executes server-side, until it produces a normal text answer.
    for _ in range(6):  # hard cap so a misbehaving loop can't run forever
        completion = client.chat.completions.create(
            model=config.SEARCH_MODEL,
            messages=messages,
            tools=WEB_SEARCH_TOOL,
            # $web_search 目前与 kimi-k2.5 的思考模式不兼容，必须关掉。
            extra_body={"thinking": {"type": "disabled"}},
        )
        choice = completion.choices[0]
        if choice.finish_reason != "tool_calls":
            return choice.message.content or ""
        messages.append(choice.message)
        for tc in choice.message.tool_calls or []:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    # For $web_search the args are echoed back; Kimi runs it itself.
                    "content": tc.function.arguments,
                }
            )
    return ""  # gave up after the cap


def _extract(client, answer):
    completion = client.chat.completions.create(
        model=config.SEARCH_MODEL,
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": answer or "（没有内容）"},
        ],
        response_format={"type": "json_object"},
        extra_body={"thinking": {"type": "disabled"}},
    )
    return json.loads(completion.choices[0].message.content)


def lookup(transcript):
    """Return a market-price record. Always reports that a search was attempted.

    {
      "searched": True,
      "price": float | None,        # None means searched but nothing reliable
      "price_text": str | None,
      "source": str | None,
    }
    """
    client = _client()
    answer = _research(client, transcript)
    try:
        data = _extract(client, answer)
    except Exception:
        data = {}

    found = bool(data.get("found")) and data.get("price") not in (None, "", 0)
    return {
        "searched": True,
        "price": data.get("price") if found else None,
        "price_text": (data.get("price_text") or None) if found else None,
        "source": (data.get("source") or None) if found else None,
    }


if __name__ == "__main__":
    # Manual smoke test: python marketprice.py "Angel Bliss bedside sleeper 2019 查原价"
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else "Angel Bliss bedside sleeper 2019 查原价"
    print("wants_lookup:", wants_lookup(q))
    print(json.dumps(lookup(q), ensure_ascii=False, indent=2))
