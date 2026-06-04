# 宝宝闲置 — 视频口述 → 一键发群

把宝宝闲置卖到微信群里的小工具。不用一件件手动拍照填表：对着摄像头一边指、一边说
（说「下一件」切下一样），手机分享给 Mac 本地跑着的小服务，它自动出一份待审的商品
列表（带挑好的图、价格、描述），你在 iPhone 浏览器里改改、勾勾图、点导出 → 图就进
了相册，正常发群即可。

整套都在你自己的设备上：

- **iPhone** 录视频、触发处理（用 iOS 快捷指令）、浏览器里审、保存图到相册。
- **Mac** 跑一个本地 Python web 服务：本地 Whisper 转写、ffmpeg 抽帧、Pillow 合成
  海报图、Claude 整理价格和描述。视频不离开 Mac，整段口述文字交给 Claude。

只在家里同 Wi-Fi 用。价格用 **美元（$）**。微信支付个人号开不了，所以不做线上收银——
买家联系你直接转账，这也是群里卖闲置最常见的方式。

## 流程

```
[iPhone] 录视频 + 说「下一件」切换
   │
   │ 视频 → 分享 → 「处理闲置」快捷指令
   ▼
[Mac · server.py]
   Whisper 转写 → 按「下一件」切段 → 每件抽帧 + 打分 → Claude 提价格/写描述
   │
   ▼
[iPhone 浏览器] 一直开着的网页，下拉刷新
   ↓
   逐件检查 → 勾图 → 改标题/价格/描述
   ↓
   点「导出原图到相册」或「导出海报图」
   ▼
[iPhone 相册] 图进相册 → 正常分享到微信群
```

## 项目结构

```
processor/
├── server.py             FastAPI 服务（接收上传、跑管线、提供网页和 API）
├── process.py            CLI 备用：本地手动跑一个视频
├── pipeline.py           核心管线：视频 → 商品（server 和 CLI 共用）
├── transcribe.py         本地 Whisper
├── segment.py            按「下一件」切段
├── frames.py             ffmpeg 抽帧 + 清晰度打分
├── enrich.py             Claude 提价/写描述
├── poster.py             Pillow 合成海报图
├── jobs.py               job 的磁盘存储
├── config.py             从 .env 读配置
├── templates/job.html    手机友好的网页
├── static/app.css        网页样式
├── shortcuts/README.md   两个 iOS 快捷指令的搭法
└── README.md             跑起来 / 日常用法 / 配置 / 常见问题
```

## 怎么跑起来

详见 [`processor/README.md`](processor/README.md)。短版：

1. **Mac 上一次性**：`pip install -r processor/requirements.txt`，复制 `.env.example`
   到 `.env`、填上 `ANTHROPIC_API_KEY` 和一个 `SERVER_TOKEN`。
2. **Mac 上每次**：`python processor/server.py`（开着就行）。
3. **iPhone 上一次性**：建两个快捷指令——「处理闲置」（分享视频用）和「保存闲置图」
   （把后端给的图存进相册）；具体步骤见 [`processor/shortcuts/README.md`](processor/shortcuts/README.md)。
4. **日常**：iPhone 录视频 → 分享给「处理闲置」→ 浏览器里刷新 → 审 → 导出 → 发群。

## 选择题（已决定的）

- **后端跑在哪**：你自己的 Mac，本地服务，不上 Anthropic 也不上腾讯云。
- **联网范围**：家里同 Wi-Fi（用 `xxx.local`）。出门要用再加 Tailscale。
- **导出形式**：原图 + 海报图（合成卡片）两种都给，按钮二选一。
- **小程序/云开发**：不要了。早期版本（带小程序）保留在 git 历史里，需要可以回看。
