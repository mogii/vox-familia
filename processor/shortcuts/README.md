# iPhone 上要建的两个 Shortcuts（按英文系统写）

整套流程只在 iPhone 的 **Shortcuts** App 里加两条捷径（不用装 App、不用越狱）。
下面所有动作名按**英文 iOS** 写（手机是英文系统就照着搜），括号里是中文对照。

> 前提：Mac 已经启动 `python server.py`。服务地址形如：
>
> ```
> http://morrys-macbook-air.local:8000
> ```
>
> （自己的主机名在 Mac 终端 `scutil --get LocalHostName` 查，加 `.local:8000`。）
>
> `.env` 里 `SERVER_TOKEN` 留空的话，下面所有 token/Authorization 相关步骤**直接跳过**。

---

## Shortcut 1：处理闲置（上传视频）

**作用**：Photos 里选中刚录的视频 → Share → 点这条捷径 → 视频自动上传到 Mac。

Shortcuts App → **+** 新建，名字随意（出现在分享面板里，建议叫 **处理闲置** 或
**Process Listing**），然后：

### 设置

- 点顶部标题旁的 ⌄（或 ⓘ 面板）→ **Show in Share Sheet**（在分享表单中显示）：开
- 点 **Receive** 那行，接收类型只勾 **Media**（媒体）（保留 **Files** 也行）

### 动作（按顺序添加，搜英文名）

1. 顶部会自动有 **Receive [Media] input from [Share Sheet]**
2. 添加 **Get Contents of URL**（获取 URL 的内容），点开箭头展开选项：
   - **URL**：`http://morrys-macbook-air.local:8000/upload`
   - **Method**：**POST**
   - **Request Body**：**Form**（表单）
     - **Add new field** → 类型选 **File**：Key 填 `file`，Value 点一下选变量
       **Shortcut Input**（快捷指令输入）
   - （只有设了 SERVER_TOKEN 才要）**Headers** → **Add new header**：
     Key `Authorization`，Value `Bearer 你的SERVER_TOKEN`
3. （可选）添加 **Show Notification**（显示通知）：内容写 `已上传，去网页等结果`

保存即可。用法：Photos 选视频 → **Share** → 往下划找到这条捷径 → 点一下。

> 局域网上传通常几秒钟。原视频留在相册里不会被改动。

---

## Shortcut 2：保存闲置图（导出到相册）

**作用**：网页里点「导出原图到相册」或「导出成品长图」→ 这条捷径被自动调起 →
把每张图存进相册。

新建捷径，**名字必须和 `.env` 里 `SAVE_SHORTCUT_NAME` 一致**——默认是
**保存闲置图**（英文系统上用中文名没问题，照打就行；想用英文名如 `SaveListingPix`
也行，但要同步改 `.env` 里的 `SAVE_SHORTCUT_NAME` 并重启 server）。

### 设置

- **Show in Share Sheet**：关（不用开）
- 网页通过 `shortcuts://` 链接调它，输入是一段文本（一个 URL）

### 动作（按顺序添加）

1. **Get Contents of URL**：
   - **URL**：点输入框 → 选变量 **Shortcut Input**
   - **Method**：**GET**（默认）
   - 返回的是 JSON 数组，例如 `["http://mac/...a.jpg", "http://mac/...b.jpg"]`
2. **Repeat with Each**（重复每个项目）：对象选上一步 **Contents of URL**
   - 循环内部添加 **Get Contents of URL**：URL 选变量 **Repeat Item**（重复项），
     Method **GET** —— 这一步把每张图下载下来
   - 循环内部再添加 **Save to Photo Album**（存储到相册）：保存对象选上一步的
     **Contents of URL**，相册 **Recents**（最近项目）即可
3. （可选）**Show Notification**：内容写 `已保存到相册`

> 第一次运行会弹权限确认（访问网络 / 添加到 Photos），都点 **Allow**。

---

## 验证

1. iPhone Safari 打开 `http://morrys-macbook-air.local:8000`（设了 token 就加
   `/?t=<token>`），看到"还没有视频"页面就对了。**Add to Home Screen**（添加到主屏幕）
   方便下次开。
2. 录一段口述视频（说「下一件」切件、想比价说「查原价」），Share → 处理闲置。
3. 回到网页：处理中会显示转圈和进度，完成后自动刷出商品列表。
4. 改改字、勾勾图、给图配句话 → 点「导出成品长图」→ 弹出 Shortcuts 跑完 →
   去 Photos 看，图应该在 **Recents** 里。

---

## 注意

- **Mac 必须开着、`server.py` 必须在跑**，手机才能上传和导图。Mac 合盖睡眠就不行了
  （System Settings → Battery 可设接电源不睡眠；或用 `caffeinate -i python server.py`
  跑，运行期间阻止睡眠）。
- **必须同一个 Wi-Fi**。`.local` 主机名靠 mDNS/Bonjour 解析；连不上时试内网 IP
  （Mac 上 `ipconfig getifaddr en0` 查，形如 `http://192.168.86.36:8000`）。
- macOS **Firewall** 如果开着会拦手机连入：System Settings → Network → Firewall，
  关掉或允许 Python 入站。
- **成品图中文字体**：靠 Mac 系统字体渲染（默认找苹方 PingFang），Mac 自带的就够。
- 如果设了 token：拿到 token 的人在同一 Wi-Fi 就能访问这个服务；快捷指令经 iCloud
  同步的话 token 也会跟着同步。
