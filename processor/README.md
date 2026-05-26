# 视频处理脚本（本地跑）

对着摄像头一件件介绍宝宝闲置，说「**下一件**」切换下一样。录完在自己电脑上跑一下脚本，
它会自动：转文字 → 按「下一件」切段 → 每件挑几张最清楚的图 → 用 Claude 听出最终价格(美元)
并写好标题和描述。你检查一下、删掉不要的图，再跑一下就发布到小程序。

整套都在你电脑本地：语音转文字用本地 Whisper，**视频不会离开你的电脑**。只有每件那段
口述文字会发给 Claude 整理价格和描述。

## 装环境（一次性）

```bash
cd processor
python3 -m venv .venv && source .venv/bin/activate   # 可选，但推荐
pip install -r requirements.txt
cp .env.example .env        # 然后编辑 .env 填上你的 key 等
```

`requirements.txt` 里的 `imageio-ffmpeg` 自带 ffmpeg，不用单独装。第一次跑 Whisper 会
自动下载模型（`small` 约几百 MB），之后就走本地缓存。

`.env` 里要填：

- `ANTHROPIC_API_KEY` — Claude 的 key（提价格 / 写描述用，费用很小）
- `CONTACT` — 你的微信号，会写进每件商品的「联系卖家」
- 发布时还要 `WX_APPID` / `WX_APPSECRET` / `WX_ENV_ID`（见下方「发布」）

## 第一步：处理视频

```bash
python process.py 我的视频.mp4
```

跑完会得到一个 `out/` 目录：

```
out/
├── transcript.txt        全部转写文字（参考用）
├── listings.json         整理好的商品列表 ← 发布前在这里检查/修改
├── item01/item01_1.jpg   第 1 件挑出来的图（不满意的直接删掉）
├── item02/...
└── ...
```

常用参数：

- `--frames 6` 每件最多挑几张图（默认 5）
- `--fps 3` 抽帧采样频率，动作快可调高（默认 2）
- `--no-ai` 不调用 Claude，只切段+挑图，价格和描述留空，全部手填

## 第二步：检查和修改

打开 `out/listings.json`，每件长这样：

```json
{
  "title": "婴儿推车",
  "price": 35,
  "condition": "9成新",
  "description": "用了大概半年，推起来很顺，折叠方便。",
  "contact": "你的微信号",
  "images": ["item01/item01_1.jpg", "item01/item01_3.jpg"],
  "transcript": "（当时你说的原话，仅供参考）"
}
```

- 价格不对就改 `price`（数字，美元）。**没听出价格的会是 `null`，必须先填上才会发布。**
- 描述、标题、成色随便改。
- 图不满意：直接去 `out/itemNN/` 删掉那张文件，或在 `images` 里删掉那一行。
- 整件不想发：把这一段从数组里删掉即可。

## 第三步：发布到小程序

```bash
python publish.py
```

它会把图片传到你的云开发存储、每件写一条到 `products` 集合。发完会给每件加上
`"published": true`，再跑一次不会重复发；想重发就把这个标记删掉。

打开小程序「逛闲置」就能看到，照常分享到微信群。

### 发布需要的云开发配置

`publish.py` 用微信云开发的服务端 HTTP 接口，只需要小程序的 AppID/AppSecret，不用
腾讯云密钥。在 `.env` 里填：

- `WX_APPID` / `WX_APPSECRET` — 在 [mp.weixin.qq.com](https://mp.weixin.qq.com) →
  「开发管理 → 开发设置」里拿。
- `WX_ENV_ID` — 云开发环境 ID。

> 如果在「开发设置 → IP 白名单」里开了限制，要把你电脑的公网 IP 加进去，否则取不到
> access_token。

## 录视频的小建议

- 一件东西讲完了再说「下一件」，停顿半秒更好切。
- 价格说清楚；临时改主意也没关系，脚本会取你**最后说定**的价。
- 想让图更好看：每件多换几个角度、光线亮一点，脚本会自动挑最清楚的。

## 暗号可以改

默认「下一件 / 下一个 / 下一样 / 下一款」都能切段。想自定义就在 `.env` 里设
`TRIGGERS=下一件,换一个`（逗号分隔）。
