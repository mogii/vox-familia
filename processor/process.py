"""Step 1: turn a narrated video into reviewable listings.

    python process.py my-video.mp4

Narrate one item at a time; say the magic word (default 下一件) to move on.
Output goes to ./out :
    out/transcript.txt        full transcript (for reference)
    out/listings.json         the listings — edit this before publishing
    out/item01/item01_1.jpg   picked frames per item — delete any you dislike

Then review and run:  python publish.py
"""

import argparse
import json
import os

import config
import frames
from enrich import enrich
from segment import find_items
from transcribe import transcribe


def main():
    ap = argparse.ArgumentParser(description="视频 → 待发布商品列表")
    ap.add_argument("video", help="录好的视频文件路径")
    ap.add_argument("--out", default="out", help="输出目录（默认 ./out）")
    ap.add_argument("--frames", type=int, default=config.FRAMES_PER_ITEM,
                    help="每件最多挑几张图")
    ap.add_argument("--fps", type=float, default=config.SAMPLE_FPS,
                    help="抽帧采样频率（每秒几帧）")
    ap.add_argument("--no-ai", action="store_true",
                    help="跳过 Claude，只切段+抽图（价格/描述留空，手动填）")
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        raise SystemExit(f"找不到视频文件：{args.video}")
    os.makedirs(args.out, exist_ok=True)

    words, full_text = transcribe(args.video)
    with open(os.path.join(args.out, "transcript.txt"), "w", encoding="utf-8") as fh:
        fh.write(full_text)
    print(f"[ok] 转写完成，共 {len(words)} 个词。")

    items = find_items(words, triggers=config.TRIGGERS)
    print(f"[ok] 按『下一件』切出 {len(items)} 件商品。")

    client = None
    if not args.no_ai:
        import anthropic

        config.require("ANTHROPIC_API_KEY")
        client_kwargs = {"api_key": config.ANTHROPIC_API_KEY}
        if config.LLM_BASE_URL:  # Moonshot/Kimi 等 Anthropic 兼容端点
            client_kwargs["base_url"] = config.LLM_BASE_URL
        client = anthropic.Anthropic(**client_kwargs)

    listings = []
    for i, item in enumerate(items, 1):
        prefix = f"item{i:02d}"
        item_dir = os.path.join(args.out, prefix)
        print(f"\n[{i}/{len(items)}] {item['start']:.1f}s–{item['end']:.1f}s  「{item['text'][:30]}…」")

        imgs = frames.best_frames(
            args.video, item["start"], item["end"],
            args.frames, args.fps, item_dir, prefix,
        )
        print(f"    挑了 {len(imgs)} 张图 -> {item_dir}")

        info = {"title": "宝宝闲置", "price": None, "condition": None,
                "description": item["text"]}
        if client is not None:
            try:
                info = enrich(item["text"], client=client)
                print(f"    {info['title']} / ${info['price']} / {info['condition']}")
            except Exception as e:
                print(f"    [warn] Claude 整理失败，留空待手填：{e}")

        listings.append(
            {
                "title": info["title"],
                "price": info["price"],
                "condition": info["condition"],
                "description": info["description"],
                "contact": config.CONTACT,
                "images": [os.path.relpath(p, args.out) for p in imgs],
                "transcript": item["text"],
            }
        )

    out_json = os.path.join(args.out, "listings.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(listings, fh, ensure_ascii=False, indent=2)

    print(f"\n[done] 写好 {len(listings)} 件 -> {out_json}")
    print("检查/修改 listings.json，删掉不要的图，然后跑：python publish.py")


if __name__ == "__main__":
    main()
