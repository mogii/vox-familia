"""Split a transcript into items by a spoken magic word (default: 下一件).

Pure logic, no external deps, so it can be unit-tested on its own.

Input is a flat list of words, each: {"text": str, "start": float, "end": float}
(seconds). Output is a list of items, each with the video time range to pull
frames from and the spoken text belonging to that item.
"""

import re

DEFAULT_TRIGGERS = ["下一件", "下一个", "下一样", "下一款", "下一件儿"]

# Characters we ignore when matching, so "下 一 件。" still matches "下一件".
_STRIP = re.compile(r"[\s,，。.!！?？、~～\-—]+")


def _normalize(text):
    return _STRIP.sub("", text or "")


def find_items(words, triggers=None):
    """Return a list of items split at each trigger phrase.

    Each item: {
        "start": float, "end": float,   # video time range for frames
        "text": str,                    # spoken description (trigger removed)
    }
    Empty stretches (e.g. two triggers back to back) are dropped.
    """
    triggers = triggers or DEFAULT_TRIGGERS
    # Longest first so "下一件儿" wins over "下一件".
    triggers = sorted(triggers, key=len, reverse=True)

    # Build a normalized character stream, remembering which word each char
    # came from so we can map match positions back to timestamps.
    chars = []  # list of (char, word_index)
    for wi, w in enumerate(words):
        for ch in _normalize(w.get("text", "")):
            chars.append((ch, wi))
    text = "".join(c for c, _ in chars)

    # Find non-overlapping trigger occurrences. Each is a char span [bs, be).
    boundaries = []
    i = 0
    n = len(text)
    while i < n:
        hit = next((t for t in triggers if text.startswith(t, i)), None)
        if hit:
            boundaries.append((i, i + len(hit)))
            i += len(hit)
        else:
            i += 1

    # Item char ranges are the gaps between (and around) the boundaries.
    cuts = [0]
    for bs, be in boundaries:
        cuts.append(bs)  # end of the item before this trigger
        cuts.append(be)  # start of the item after this trigger
    cuts.append(n)

    items = []
    for k in range(0, len(cuts), 2):
        lo, hi = cuts[k], cuts[k + 1]
        if hi <= lo:
            continue
        word_idxs = sorted({chars[c][1] for c in range(lo, hi)})
        if not word_idxs:
            continue
        item_words = [words[wi] for wi in word_idxs]
        item_text = "".join(w.get("text", "") for w in item_words).strip()
        if not item_text:
            continue
        items.append(
            {
                "start": float(item_words[0]["start"]),
                "end": float(item_words[-1]["end"]),
                "text": item_text,
            }
        )
    return items


if __name__ == "__main__":
    # Quick self-test with synthetic word timings.
    def words(spec):
        out, t = [], 0.0
        for tok in spec:
            out.append({"text": tok, "start": t, "end": t + 1})
            t += 1
        return out

    # Two items separated by one trigger.
    w = words(["这", "是", "一", "件", "外套", "下一件", "这", "双", "鞋子"])
    items = find_items(w)
    assert len(items) == 2, items
    assert "外套" in items[0]["text"] and "下一件" not in items[0]["text"]
    assert "鞋子" in items[1]["text"]
    assert items[0]["start"] == 0.0 and items[0]["end"] == 5.0
    assert items[1]["start"] == 6.0

    # No trigger -> single item spanning everything.
    one = find_items(words(["一", "块", "积木"]))
    assert len(one) == 1 and one[0]["start"] == 0.0

    # Trigger split across tokens with punctuation in between.
    split = find_items(
        [
            {"text": "围嘴", "start": 0, "end": 1},
            {"text": "下", "start": 1, "end": 1.3},
            {"text": "一", "start": 1.3, "end": 1.6},
            {"text": "件，", "start": 1.6, "end": 2},
            {"text": "睡袋", "start": 2, "end": 3},
        ]
    )
    assert len(split) == 2, split
    assert split[0]["text"].startswith("围嘴")
    assert "睡袋" in split[1]["text"]

    # Back-to-back triggers produce no empty item.
    bb = find_items(words(["帽子", "下一件", "下一件", "手套"]))
    assert len(bb) == 2, bb

    print("segment.py self-test passed:", len(items), "items in main case")
