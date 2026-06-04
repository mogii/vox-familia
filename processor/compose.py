"""Compose one listing's chosen photos into a single tall image for WeChat.

Layout: selected photos stacked top-to-bottom into ONE image.
- Under the FIRST photo: a white info card (title / price / ~~原价~~ / condition
  / description).
- Under EVERY photo: the optional one-line caption the seller typed for it.

Works off the job data model: listing["candidates"] (all frames),
listing["selected"] (indices), listing["captions"] ({index-as-str: text}).
"""

import os

from PIL import Image, ImageDraw, ImageFont

import config

WIDTH = 1080          # WeChat-friendly width
SIDE = 48             # left/right padding inside cards
GAP = 16              # vertical gap between stacked blocks
BG = (245, 246, 248)  # canvas background
CARD_BG = (255, 255, 255)
INK = (34, 34, 34)
GREY = (140, 140, 140)
ORANGE = (255, 90, 44)
TAG_BG = (241, 241, 241)

_FONT_CACHE = {}


def _font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for path in config.POSTER_FONT.split(":"):
        if path and os.path.isfile(path):
            try:
                f = ImageFont.truetype(path, size)
                _FONT_CACHE[size] = f
                return f
            except Exception:
                continue
    f = ImageFont.load_default()
    _FONT_CACHE[size] = f
    return f


def _wrap(draw, text, font, max_width):
    """Wrap text to max_width. Works for CJK (per-char) and spaced words."""
    lines = []
    for paragraph in (text or "").split("\n"):
        if not paragraph:
            lines.append("")
            continue
        line = ""
        for ch in paragraph:
            trial = line + ch
            if draw.textlength(trial, font=font) <= max_width or not line:
                line = trial
            else:
                lines.append(line)
                line = ch
        lines.append(line)
    return lines


def _text_height(font):
    asc, desc = font.getmetrics()
    return asc + desc


def _fit_photo(path):
    img = Image.open(path).convert("RGB")
    h = round(img.height * WIDTH / img.width)
    return img.resize((WIDTH, h))


def _caption_block(text):
    """A white strip with the seller's per-photo note. None if empty."""
    text = (text or "").strip()
    if not text:
        return None
    font = _font(34)
    scratch = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = _wrap(scratch, text, font, WIDTH - 2 * SIDE)
    lh = _text_height(font) + 8
    h = 24 + lh * len(lines) + 24
    block = Image.new("RGB", (WIDTH, h), CARD_BG)
    d = ImageDraw.Draw(block)
    y = 24
    for ln in lines:
        d.text((SIDE, y), ln, font=font, fill=INK)
        y += lh
    return block


def _num(v):
    """Render a price without a trailing .0 (35.0 -> 35, 12.5 -> 12.5)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return int(f) if f == int(f) else round(f, 2)


def _info_card(listing, currency):
    """The main white card: title, price + 原价, condition tag, description."""
    title_f = _font(46)
    price_f = _font(60)
    orig_f = _font(34)
    cond_f = _font(30)
    desc_f = _font(36)

    scratch = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    title_lines = _wrap(scratch, listing.get("title") or "宝宝闲置", title_f, WIDTH - 2 * SIDE)
    desc_lines = _wrap(scratch, listing.get("description") or "", desc_f, WIDTH - 2 * SIDE)

    title_lh = _text_height(title_f) + 10
    desc_lh = _text_height(desc_f) + 10
    price_h = _text_height(price_f)

    h = 36
    h += title_lh * len(title_lines) + 20
    h += price_h + 24
    if desc_lines and any(desc_lines):
        h += desc_lh * len(desc_lines)
    h += 36

    card = Image.new("RGB", (WIDTH, h), CARD_BG)
    d = ImageDraw.Draw(card)
    y = 36

    for ln in title_lines:
        d.text((SIDE, y), ln, font=title_f, fill=INK)
        y += title_lh
    y += 20

    # Price line: big orange price, then struck-through 原价, then condition tag.
    price = listing.get("price")
    price_text = f"{currency}{_num(price)}" if price is not None else f"{currency}—"
    d.text((SIDE, y), price_text, font=price_f, fill=ORANGE)
    x = SIDE + d.textlength(price_text, font=price_f) + 24

    market = (listing.get("marketPriceText") or "").strip() or (
        f"{currency}{_num(listing['marketPrice'])}" if listing.get("marketPrice") else None
    )
    if market:
        label = f"原价 {market}"
        baseline = y + price_h - _text_height(orig_f)
        d.text((x, baseline), label, font=orig_f, fill=GREY)
        lw = d.textlength(label, font=orig_f)
        ly = baseline + _text_height(orig_f) // 2
        d.line((x, ly, x + lw, ly), fill=GREY, width=3)
        x += lw + 24

    cond = (listing.get("condition") or "").strip()
    if cond:
        pad = 14
        cw = d.textlength(cond, font=cond_f) + pad * 2
        ch = _text_height(cond_f) + 12
        cy = y + price_h - ch
        d.rounded_rectangle((x, cy, x + cw, cy + ch), radius=10, fill=TAG_BG)
        d.text((x + pad, cy + 6), cond, font=cond_f, fill=GREY)

    y += price_h + 24

    for ln in desc_lines:
        if ln:
            d.text((SIDE, y), ln, font=desc_f, fill=(85, 85, 85))
        y += desc_lh

    return card


def _stack(blocks):
    blocks = [b for b in blocks if b is not None]
    total = sum(b.height for b in blocks) + GAP * (len(blocks) + 1)
    canvas = Image.new("RGB", (WIDTH, total), BG)
    y = GAP
    for b in blocks:
        canvas.paste(b, (0, y))
        y += b.height + GAP
    return canvas


def compose(item_dir, listing, currency="$"):
    """Build the composite for one listing; return a Pillow Image.

    Photos = listing["selected"] indices into listing["candidates"], in time
    order. Per-photo captions come from listing["captions"][str(index)].
    """
    candidates = listing.get("candidates") or []
    selected = [i for i in (listing.get("selected") or []) if 0 <= i < len(candidates)]
    if not selected:
        raise ValueError("请先选至少一张图")
    captions = listing.get("captions") or {}

    blocks = []
    for pos, idx in enumerate(selected):
        photo_path = os.path.join(item_dir, candidates[idx]["filename"])
        blocks.append(_fit_photo(photo_path))
        if pos == 0:
            blocks.append(_info_card(listing, currency))
        blocks.append(_caption_block(captions.get(str(idx))))

    return _stack(blocks)


def render_to(path, item_dir, listing, currency="$"):
    img = compose(item_dir, listing, currency=currency)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "JPEG", quality=90)
    return path
