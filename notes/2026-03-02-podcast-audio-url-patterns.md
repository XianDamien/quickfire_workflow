# 播客音频 URL 的三种模式

## 1. 媒体选择器/重定向代理（BBC）

```
http://open.live.bbc.co.uk/mediaselector/6/redir/version/2.0/mediaset/audio-nondrm-download-rss-low/proto/http/vpid/p0n3yxyc.mp3
```

- URL 本身不指向实际文件，是一个**中间代理层**
- 后端根据 `vpid`（节目 ID）查找实际存储地址，返回 302 跳转
- 好处：可随时更换 CDN/存储位置而不用改 RSS；按地区/协议返回不同源；统计下载量
- 代表：BBC、大型媒体机构自建媒体服务

## 2. 内容寻址存储（Substack）

```
https://api.substack.com/feed/podcast/188846384/24716a31c4c42fdb82ccbe05ad197054.mp3
```

结构：`/feed/podcast/{post_id}/{md5_hash}.mp3`

- `188846384`：文章/集数的数据库 Post ID
- `24716a31c4c42fdb82ccbe05ad197054`：文件内容的 **MD5 哈希**（32位十六进制）

MD5 作为文件名的优势：
- **去重**：相同内容只存一份
- **CDN 缓存友好**：文件名不变 → 可永久缓存
- **防猜测**：无法通过自增 ID 遍历他人文件
- **完整性校验**：可验证下载内容未损坏

类似方案的平台/服务：AWS S3、Cloudflare R2、阿里云 OSS、Backblaze B2、Buzzsprout 等播客托管平台

## 3. 多层前缀追踪（NPR / 商业播客）

```
https://tracking.swap.fm/track/XvDEoI11TR00olTUO8US/prfx.byspotify.com/e/play.podtrac.com/npr-510289/traffic.megaphone.fm/NPR3715588590.mp3?t=podcast&e=nx-s1-5720653&p=510289&d=2164&size=34627170
```

套娃结构（从外到内）：

| 层 | 服务 | 角色 |
|---|---|---|
| `tracking.swap.fm` | swap.fm | 第三方广告/分析平台 |
| `prfx.byspotify.com` | Spotify 前缀追踪 | Spotify 自己的收听统计 |
| `play.podtrac.com` | Podtrac | IAB 认证第三方测量机构 |
| `traffic.megaphone.fm` | Megaphone（Spotify旗下） | 实际音频托管 |

Query 参数含义：
- `e=` 集数 ID
- `p=` 节目 ID
- `d=` 时长（秒）
- `size=` 文件大小（字节）

**工作原理**：每层都是 302 重定向 → 记录日志 → 转发给下一层 → 最终返回实际 MP3

**为什么要这样**：播客收听数据是广告定价的核心依据。前缀追踪写在 RSS `<enclosure>` URL 里，播客客户端无感知，每次下载请求会被多个数据平台同时记录。

---

## 共同基础：RSS `<enclosure>` 标签

三种模式的 URL 最终都写在 RSS feed 里：

```xml
<enclosure
  url="https://..."
  type="audio/mpeg"
  length="34627170"
/>
```

播客客户端（Podcast Addict 等）解析 RSS，存储原始 URL，下载完成后仍展示给用户。
