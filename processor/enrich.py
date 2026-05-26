"""Turn one item's spoken transcript into a listing: price + title + description.

Uses Claude. The model only sees the transcript text (cheap), and is told to
stick to what was actually said — no inventing prices or specs.
"""

import json

import config

CONDITIONS = ["全新", "9成新", "8成新", "7成新及以下"]

SYSTEM = (
    "你在帮一位妈妈把口述的二手宝宝用品整理成挂在小程序上的商品信息。"
    "她会对着摄像头随口介绍一件东西，可能临时改主意改价格。请只依据她说的内容整理，"
    "不要编造没提到的细节。价格一律理解为美元(USD)。"
    "如果她改了价（比如『卖5刀…算了3刀吧』），取她最后说定的价格。"
    "如果她完全没说价格，price 返回 null。description 用自然、亲切的中文，"
    "1～3句话，面向买家，可适当润色但不得虚构成色或功能。"
)

TOOL = {
    "name": "listing",
    "description": "整理后的单件商品信息",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "简短标题，10字以内"},
            "price": {
                "type": ["number", "null"],
                "description": "美元价格数字；没提到则为 null",
            },
            "condition": {
                "type": ["string", "null"],
                "enum": CONDITIONS + [None],
                "description": "成色，从给定选项里挑最接近的；没线索则 null",
            },
            "description": {"type": "string", "description": "面向买家的中文描述"},
        },
        "required": ["title", "price", "condition", "description"],
    },
}


def enrich(transcript, client=None):
    """Return {title, price, condition, description} for one item's transcript."""
    import anthropic

    client = client or anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    resp = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=600,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "listing"},
        messages=[{"role": "user", "content": f"她说的是：\n{transcript}"}],
    )

    for block in resp.content:
        if block.type == "tool_use" and block.name == "listing":
            data = block.input
            return {
                "title": (data.get("title") or "").strip() or "宝宝闲置",
                "price": data.get("price"),
                "condition": data.get("condition"),
                "description": (data.get("description") or "").strip(),
            }

    # Shouldn't happen with forced tool_choice, but fail soft.
    return {
        "title": "宝宝闲置",
        "price": None,
        "condition": None,
        "description": transcript.strip(),
    }
