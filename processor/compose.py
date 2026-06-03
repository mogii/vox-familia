"""Compose one listing's chosen photos into a single tall image for WeChat.

Layout (chosen design): photos stacked top-to-bottom into one image.
- Under the FIRST photo: a white info card (title / price / 原价 / description).
- Under EVERY chosen photo (incl. the first): an optional caption the seller
  typed for that specific photo.

Pure Pillow, uses a macOS CJK font. Self-test at the bottom builds a synthetic
listing so you can eyeball the result without running a whole video.
"""

import os

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080          # WeChat-friendly width
SIDE = 48             # left/right padding inside cards
GAP = 16             # vertical gap between stacked blocks
BG = (245, 246, 248)  # canvas background
CARD_BG = (255, 255, 255)
INK = (34, 34, 34)
GREY = (140, 140, 140)
ORANGE = (255, 90, 44)
TAG_BG = (241, 241, 241)

# macOS CJK fonts, tried in order. Index picks a face inside a .ttc.
FONT_CANDIDATES = [
    ("/System/Library/Fonts/PingFang.ttc", 0),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
    ("/Library/Fonts/Arial Unicode.ttf", 0),
]


def _font(size):
    for path, idx in FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size, index=idx)
            except Exception:
                continue
    return ImageFont.load_default()


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


def _info_card(listing):
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
    price_text = f"${_num(price)}" if price is not None else "$—"
    d.text((SIDE, y), price_text, font=price_f, fill=ORANGE)
    x = SIDE + d.textlength(price_text, font=price_f) + 24

    market = listing.get("marketPriceText") or (
        f"${_num(listing['marketPrice'])}" if listing.get("marketPrice") else None
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


def _num(v):
    """Render a price without a trailing .0 (35.0 -> 35, 12.5 -> 12.5)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return int(f) if f == int(f) else round(f, 2)


def _stack(blocks):
    blocks = [b for b in blocks if b is not None]
    total = sum(b.height for b in blocks) + GAP * (len(blocks) + 1)
    canvas = Image.new("RGB", (WIDTH, total), BG)
    y = GAP
    for b in blocks:
        canvas.paste(b, (0, y))
        y += b.height + GAP
    return canvas


def compose_listing(listing, base_dir, out_path):
    """Build the single composite image for one listing; save to out_path.

    Uses listing["selectedImages"] (ordered subset) if present, else all
    listing["images"]. Per-photo notes come from listing["imageCaptions"].
    """
    images = listing.get("selectedImages") or listing.get("images") or []
    captions = listing.get("imageCaptions") or {}
    if not images:
        raise ValueError("这件没有可用图片")

    blocks = []
    for idx, rel in enumerate(images):
        photo = _fit_photo(os.path.join(base_dir, rel))
        blocks.append(photo)
        if idx == 0:
            blocks.append(_info_card(listing))
        blocks.append(_caption_block(captions.get(rel)))

    canvas = _stack(blocks)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, quality=90)
    return out_path


if __name__ == "__main__":
    # Self-test: synthesize two photos + a listing, compose, and report size.
    import tempfile

    tmp = tempfile.mkdtemp()
    for name, color in [("a.jpg", (120, 170, 210)), ("b.jpg", (210, 170, 120))]:
        Image.new("RGB", (1200, 900), color).save(os.path.join(tmp, name))

    demo = {
        "title": "Angel Bliss 婴儿床边睡篮",
        "price": 35,
        "condition": "9成新",
        "description": "2019 款，用过几个月，结构很稳，可调高度。\n无破损，烟酒宠物 free 家庭。",
        "marketPriceText": "$169.99–$199.99",
        "marketPrice": 184.99,
        "selectedImages": ["a.jpg", "b.jpg"],
        "imageCaptions": {"b.jpg": "侧面：高度调节卡扣完好"},
    }
    out = compose_listing(demo, tmp, os.path.join(tmp, "post.jpg"))
    im = Image.open(out)
    print(f"composed OK -> {out}  size={im.size}")
