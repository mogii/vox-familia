"""Step 2: upload reviewed listings to 微信云开发.

    python publish.py            # publishes everything in out/listings.json

Images go to cloud storage, one document per item is written into the
`products` collection, and your storefront mini-program shows them right away.

Each item in listings.json may carry "published": true (added after a
successful upload) so re-running won't create duplicates. Delete that flag to
force a re-publish.
"""

import argparse
import json
import os
import time

import config
import wxcloud


def _missing_images(images, base):
    return [p for p in images if not os.path.isfile(os.path.join(base, p))]


def main():
    ap = argparse.ArgumentParser(description="把 out/listings.json 发布到云开发")
    ap.add_argument("--out", default="out", help="process.py 的输出目录")
    ap.add_argument("--file", help="listings.json 路径（默认 <out>/listings.json）")
    args = ap.parse_args()

    base = args.out
    path = args.file or os.path.join(base, "listings.json")
    if not os.path.isfile(path):
        raise SystemExit(f"找不到 {path}，请先跑 process.py。")

    appid = config.require("WX_APPID")
    secret = config.require("WX_APPSECRET")
    env = config.require("WX_ENV_ID")

    with open(path, encoding="utf-8") as fh:
        listings = json.load(fh)

    token = wxcloud.get_access_token(appid, secret)
    published = 0

    for i, item in enumerate(listings):
        if item.get("published"):
            continue
        if item.get("price") in (None, ""):
            print(f"[skip] 第 {i + 1} 件没有价格，先在 listings.json 里填上再发。")
            continue

        images = item.get("images", [])
        missing = _missing_images(images, base)
        if not images or missing:
            print(f"[skip] 第 {i + 1} 件图片缺失或为空：{missing or '无图'}")
            continue

        file_ids = []
        for j, rel in enumerate(images):
            ext = os.path.splitext(rel)[1].lstrip(".") or "jpg"
            cloud_path = f"products/{int(time.time())}_{i}_{j}.{ext}"
            file_ids.append(
                wxcloud.upload_file(token, env, cloud_path, os.path.join(base, rel))
            )

        doc = {
            "title": item.get("title") or "宝宝闲置",
            "price": float(item["price"]),
            "condition": item.get("condition") or "",
            "desc": item.get("description") or "",
            "contact": item.get("contact") or config.CONTACT,
            "images": file_ids,
            "status": "available",
            "createTime": int(time.time() * 1000),
        }
        ids = wxcloud.db_add(token, env, config.PRODUCTS_COLLECTION, [doc])
        item["published"] = True
        published += 1
        print(f"[ok] 已发布：{doc['title']}  ${doc['price']}  (id={ids})")

    # Persist the published flags so re-runs are idempotent.
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(listings, fh, ensure_ascii=False, indent=2)

    print(f"\n[done] 本次发布 {published} 件。打开小程序「逛闲置」即可看到。")


if __name__ == "__main__":
    main()
