"""Compose a square-ish listing card: photo + title/price/description text.

The output is meant to be shared straight into a WeChat group as one image.
Requires a CJK-capable font on the system (configured via POSTER_FONT).
"""

import os

from PIL import Image, ImageDraw, ImageFont

import config

CARD_W, CARD_H = 1080, 1350
PAD = 60
PHOTO_BOX = (PAD, 220, CARD_W - PAD, 220 + 720)   # left, top, right, bottom

_FONT_CACHE = {}


def _font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for candidate in config.POSTER_FONT.split(":"):
        if candidate and os.path.isfile(candidate):
            try:
                f = ImageFont.truetype(candidate, size=size)
                _FONT_CACHE[size] = f
                return f
            except Exception:
                pass
    f = ImageFont.load_default()
    _FONT_CACHE[size] = f
    return f


def _wrap(draw, text, font, max_width):
    """Wrap a Chinese/English string into lines that fit `max_width`."""
    lines, line = [], ""
    for ch in text or "":
        if ch == "\n":
            lines.append(line)
            line = ""
            continue
        trial = line + ch
        w = draw.textbbox((0, 0), trial, font=font)[2]
        if w > max_width and line:
            lines.append(line)
            line = ch
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _fit_photo(img, box):
    bw, bh = box[2] - box[0], box[3] - box[1]
    iw, ih = img.size
    scale = max(bw / iw, bh / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - bw) // 2
    top = (nh - bh) // 2
    return img.crop((left, top, left + bw, top + bh))


def compose(photo_path, listing, currency="$"):
    """Compose a card for one listing and return a Pillow Image."""
    canvas = Image.new("RGB", (CARD_W, CARD_H), "white")
    draw = ImageDraw.Draw(canvas)

    title_font = _font(64)
    price_font = _font(80)
    desc_font = _font(38)
    meta_font = _font(28)

    # Title (single line, truncate if needed).
    title = (listing.get("title") or "").strip() or "宝宝闲置"
    max_title_w = CARD_W - 2 * PAD
    while draw.textbbox((0, 0), title, font=title_font)[2] > max_title_w and len(title) > 1:
        title = title[:-1]
    draw.text((PAD, 60), title, font=title_font, fill="#222222")

    # Price (right of title row).
    price = listing.get("price")
    if price is not None:
        price_str = f"{currency}{price:g}" if isinstance(price, (int, float)) else f"{currency}{price}"
        pw = draw.textbbox((0, 0), price_str, font=price_font)[2]
        draw.text((CARD_W - PAD - pw, 50), price_str, font=price_font, fill="#ff5a2c")

    # Photo, cover-cropped into PHOTO_BOX.
    if photo_path and os.path.isfile(photo_path):
        with Image.open(photo_path) as im:
            im = im.convert("RGB")
            cropped = _fit_photo(im, PHOTO_BOX)
            canvas.paste(cropped, (PHOTO_BOX[0], PHOTO_BOX[1]))
    else:
        draw.rectangle(PHOTO_BOX, fill="#eeeeee")
        draw.text((PHOTO_BOX[0] + 20, PHOTO_BOX[1] + 20), "(无图)", font=desc_font, fill="#999999")

    # Description block under the photo.
    desc = (listing.get("description") or "").strip()
    if desc:
        lines = _wrap(draw, desc, desc_font, CARD_W - 2 * PAD)[:5]
        y = PHOTO_BOX[3] + 30
        for line in lines:
            draw.text((PAD, y), line, font=desc_font, fill="#333333")
            y += desc_font.size + 12

    # Meta footer: condition + contact.
    meta_parts = []
    if listing.get("condition"):
        meta_parts.append(listing["condition"])
    contact = listing.get("contact") or ""
    if contact:
        meta_parts.append(f"微信 {contact}")
    if meta_parts:
        meta = "    ".join(meta_parts)
        draw.text((PAD, CARD_H - PAD - meta_font.size), meta, font=meta_font, fill="#888888")

    return canvas


def render_to(path, photo_path, listing, currency="$"):
    img = compose(photo_path, listing, currency=currency)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "JPEG", quality=92)
    return path
