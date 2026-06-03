# 宝宝闲置 · 视频转成品图

一个帮你在微信群里卖宝宝闲置的本地小工具。不用一件件手动拍照填表，也不用做小程序：

> **对着摄像头把要卖的东西一件件说一遍**（说「下一件」切换，想查价就说「查原价」）
> → 电脑上跑两步 → 得到一张张**可直接发群的成品图**（照片 + 价格 + 原价 + 描述）。

卖东西还是用你最习惯的方式——在群里一张张发图。这个工具只是帮你把「整理 + 配文 + 排版」
这件最烦的事自动化了。全程在你电脑本地跑，视频不外传。

## 流程

```
录视频(边说边介绍, 说「下一件」切换, 想查价说「查原价」)
        │
        ▼  电脑本地，python process.py 视频.mov
  转文字 → 切段 → 每件挑最清晰的图 → 大模型提价格/写描述 →（查原价的）联网搜参考价
        │
        ▼  python webapp.py  → 浏览器里
  每件挑用哪几张图 / 改标题价格描述 / 给每张图加一句话 → 一键合成「一张长图」
        │
        ▼
  out/posts/ 里的成品图，一张张发微信群
```

## 项目结构

```
.
└── processor/                 本地脚本 + 网页（见 processor/README.md）
    ├── process.py             视频 → out/listings.json + 每件挑好的图
    ├── webapp.py              本地网页：挑图/改字/加文字/生成成品图
    ├── compose.py             把多张图合成一张长图（印标题/价格/原价/描述）
    ├── marketprice.py         「查原价」联网搜新品参考价（Kimi $web_search）
    ├── transcribe.py          本地 Whisper 语音转文字
    ├── segment.py             按「下一件」切段
    ├── frames.py              抽帧并挑最清晰的几张
    ├── enrich.py              大模型提价格 / 写标题描述
    └── README.md              详细使用说明
```

## 快速开始

都在 `processor/` 目录里，详见 [`processor/README.md`](processor/README.md)：

```bash
cd processor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 填上大模型 key（官方 Claude 或 Moonshot/Kimi）

python process.py 我的视频.mov  # 第一步：视频 → out/
python webapp.py               # 第二步：浏览器开 http://127.0.0.1:5000 整理并生成成品图
```

## 关于价格

价格用**美元（$）**。这个工具不经手任何支付——买家在群里看中后照你平时的方式私聊、
转账即可。「原价」是大模型联网搜到的**新品参考价**，只在你录视频时说了「查原价」的那件才有，
都当参考、可随时改或删。

## 大模型 / 隐私

- 语音转文字：**本地** Whisper，视频和音频不出你电脑。
- 价格/描述、联网查原价：把那一小段**文字**发给大模型（官方 Claude 或 Moonshot/Kimi，
  用你自己的 key）。费用很小。
- 没有服务器、没有云数据库、不上传任何图片。成品图只存在你本地 `out/posts/`。
