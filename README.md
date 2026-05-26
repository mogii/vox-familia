# 宝宝闲置小铺

在微信群里卖宝宝闲置用品的小工具。卖东西的人**不用一件件手动拍照填表**：对着摄像头
把要卖的东西一件件说一遍（说「下一件」切换），在自己电脑上跑个脚本，它就自动转成
一条条商品（挑好图、听出价格、写好描述）发布到小程序，群里的人打开就能逛、就能买。

整体分两块：

- **`processor/`** — 本地 Python 脚本：视频 → 商品。语音转文字在本地跑（视频不出你电脑），
  只有口述文字交给 Claude 整理价格和描述。详见 [`processor/README.md`](processor/README.md)。
- **`miniprogram/`** — 微信小程序（基于云开发，不用买服务器）：群里的人逛闲置、看详情、
  复制联系方式、分享到群；你自己能标记「已售」「删除」。商品由脚本发布，小程序里没有
  手动发布页。

> 价格用**美元（$）**。微信支付需要企业资质，个人号开不了，所以不做线上收银 —— 买家
> 看中后照着联系方式加你微信、直接转账，这也是群里卖闲置最常见的方式。

## 整体流程

```
录视频(边说边介绍, 说「下一件」切换)
        │
        ▼  电脑本地
  python process.py 视频.mp4   → 转文字 → 切段 → 挑图 → Claude 提价格/写描述
        │
        ▼  你检查 out/listings.json，删掉不要的图、改改价格
  python publish.py            → 传图 + 写入云开发 products 集合
        │
        ▼
  小程序「逛闲置」立刻能看到 → 分享到微信群
```

## 项目结构

```
.
├── processor/                   本地处理脚本（见 processor/README.md）
│   ├── process.py               视频 → out/listings.json + 图片
│   ├── publish.py               out/ → 微信云开发
│   └── ...
├── miniprogram/                 小程序前端
│   ├── config.js                ← 填云环境 ID 和你的 openid
│   └── pages/
│       ├── index/               逛闲置（首页）
│       ├── detail/              商品详情 + 分享
│       └── mine/                管理（标记已售/恢复/删除，仅你可见）
├── cloudfunctions/
│   └── login/                   云函数：返回当前用户 openid
└── project.config.json          ← 填你的小程序 AppID
```

## 小程序怎么跑起来

### 1. 申请小程序、装工具
1. 在 [微信公众平台](https://mp.weixin.qq.com) 注册小程序，拿到 **AppID**（个人主体即可）。
2. 装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)。

### 2. 导入项目
1. 开发者工具 →「导入项目」→ 选本仓库根目录。
2. 把 `project.config.json` 里的 `appid` 改成你自己的。

### 3. 开通云开发
1. 开发者工具顶部点 **「云开发」**，按提示开通（个人账号有免费额度）。
2. 创建环境，复制**环境 ID**（形如 `baby-resale-2xxxxx`），填到 `miniprogram/config.js`
   的 `cloudEnv`。

### 4. 建数据库集合 + 设权限
1. 「云开发控制台 → 数据库」新建集合，名字必须是 **`products`**。
2. 这个集合的发布由本地脚本（管理端）完成，标记已售/删除由你本人在小程序里操作。
   把权限设成**自定义安全规则**：

   ```json
   {
     "read": true,
     "write": "auth.openid == \"你的OPENID\""
   }
   ```

   这样所有人都能逛，只有你能改/删。

### 5. 部署 login 云函数
1. 左侧文件树右键 `cloudfunctions/login`。
2. 选 **「上传并部署：云端安装依赖」**。

### 6. 填上你的 openid
1. 编译运行一次，在控制台看到 `login` 云函数返回的 `openid`，复制它。
2. 填到 `miniprogram/config.js` 的 `ownerOpenid`，也填进上面第 4 步的安全规则里。
   （这样「管理」页和详情页的管理按钮只对你显示。）

### 7. 发布第一批商品
按 [`processor/README.md`](processor/README.md) 在电脑上处理一个视频并 `publish.py`，
然后小程序「逛闲置」刷新即可看到。

## 常见问题

- **「逛闲置」一直加载失败**：多半是 `config.js` 的环境 ID 没填对，或 `products` 集合没建。
- **看不到「标记已售/删除」按钮**：确认 `config.js` 的 `ownerOpenid` 是你本人的、`login`
  云函数已部署。
- **`publish.py` 报取不到 access_token**：检查 AppID/AppSecret，以及云开发/小程序后台的
  IP 白名单是否放行了你电脑的公网 IP。

## 上线

测试没问题后，在开发者工具点「上传」，再到微信公众平台「版本管理」提交审核、发布。
