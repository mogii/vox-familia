# 宝宝闲置 — Mac 上的本地服务

对着摄像头一件件介绍宝宝闲置，说「**下一件**」切下一样。手机分享视频到 Mac 上跑着
的这个服务，它自动转写、切段、挑图、用 Claude 提价格写描述，然后你在 iPhone 浏览器
里检查、改、勾图，导出到相册——之后随手发到微信群里就行。

所有处理都在你 Mac 本地：Whisper 跑在本地，**视频不离开你电脑**；只有每件那段口述
文字会发给 Claude 整理价格和描述。

## 一次性环境准备

### 1. 装 Python 依赖

```bash
cd processor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 然后编辑 .env
```

`requirements.txt` 里的 `imageio-ffmpeg` 自带 ffmpeg；第一次跑 Whisper 会自动下载
模型（`small` 约几百 MB）。

`.env` 必填：

- `ANTHROPIC_API_KEY` — Claude 的 key（费用很小）
- `CONTACT` — 你的微信号（写进每件商品）
- `SERVER_TOKEN` — 随便填一个长字符串（手机端会带这个 token）

### 2. 启动服务

```bash
python server.py
```

输出里会写明端口（默认 8000）。Mac 系统设置 →「共享 → 本地主机名」里能看到 Mac 的
`.local` 地址，例如 `nicks-macbook.local`。验证一下：

```
http://nicks-macbook.local:8000/?t=<你的SERVER_TOKEN>
```

iPhone 浏览器打开这个地址（保持在前台），看到"还没有视频"就对了。把它加到主屏方便
下次开。

### 3. 在 iPhone 上建两个快捷指令

见 [`shortcuts/README.md`](shortcuts/README.md)，两条都是几个动作的事，5 分钟搞定：

- **处理闲置**：照片分享面板里的入口，把视频上传给 Mac。
- **保存闲置图**：被网页按钮调起，把导出图存到相册。

---

## 日常用法

1. **录视频**：iPhone 录像，一件件介绍，说「下一件」切下一样。可以临时改价（脚本会取你
   **最后说定**的那个）。
2. **触发处理**：照片里找到这条视频 → 分享 → 选「处理闲置」。手机会推一条通知"已上传"。
3. **去看结果**：iPhone 浏览器里那个一直开着的页面下拉刷新（或等它自己刷新）。处理
   完会看到一条条商品。
4. **审一下**：每件可以改标题/价格/成色/描述；点缩略图勾上/取消想要的照片。
5. **导出**：每件下面两个按钮——
   - 「导出原图到相册」：把你勾的几张原图存进相册
   - 「导出海报图」：合成一张"图+标题+价格+描述"的卡片图存进相册
6. **发群**：相册里挑刚存进去的图，正常分享到微信群即可。

---

## 命令行备用

不想用手机也行：

```bash
python process.py 我的视频.mp4
```

会建一个新的 job，处理完后 `python server.py` 起来，浏览器打开 `/` 就能审。

---

## 暗号、模型、参数

`.env` 里能调的：

- `TRIGGERS=下一件,换一个` — 切段暗号（逗号分隔；默认四个）
- `FRAMES_PER_ITEM=5` — 每件默认勾几张图（你可以在网页里增减）
- `SAMPLE_FPS=2` — 抽帧采样频率（动作快可调高）
- `WHISPER_MODEL=small` — 准/慢权衡（tiny / base / small / medium / large-v3）
- `CLAUDE_MODEL=claude-sonnet-4-6` — 默认这个，价格低又够用

---

## 数据放哪儿

所有处理结果在 `processor/jobs/<id>/`：

```
jobs/abc1234567/
├── 你的视频.mov         上传的原视频
├── state.json          这个 job 的状态、各件商品的数据
├── items/0/...jpg      第 1 件的所有候选帧
├── items/1/...jpg      ...
└── posters/0.jpg       第 1 件的海报图（按需生成、按需清除）
```

不需要的 job 直接 `rm -rf jobs/<id>` 删掉就行（页面会自动跳到下一个最近的）。

`.env` 和 `jobs/` 都在 `.gitignore` 里，不会进仓库。

---

## 常见问题

- **手机打不开 `nicks-macbook.local:8000`**：
  - Mac 上 `server.py` 还在跑吗？
  - 手机和 Mac 在同一个 Wi-Fi 吗？
  - 浏览器试试 Mac 的内网 IP，例如 `http://192.168.1.42:8000/?t=...`。
  - macOS 的「防火墙」如果开着，会拦住外部连入；要么关掉，要么允许 Python 入站。
- **海报图里中文是方块**：Mac 上没找到 CJK 字体。`.env` 里 `POSTER_FONT` 指到一个
  存在的字体文件（系统自带的 `/System/Library/Fonts/PingFang.ttc` 一般都在）。
- **`No module named 'faster_whisper'`** 之类**：`pip install -r requirements.txt`
  漏了，重装一下。
- **AI 整理偶尔会乱**：每件下面有「当时说的原话」可以展开比对；不满意直接手动改。
