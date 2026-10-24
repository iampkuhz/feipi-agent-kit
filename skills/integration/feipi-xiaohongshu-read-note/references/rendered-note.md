# 已有浏览器会话的可见页面取证

匿名访问返回登录页、验证码或应用外壳时，先保留该次 manifest。宿主若有用户正常浏览器会话，可通过环境提供的原生页面工具打开同一原链接，读取可见的标题、作者、正文、发布日期显示和图文轮播图；不读取/导出 Cookie、浏览器凭据、localStorage，不调用未核验的解析服务。页面仍不可读则停止该分支，如实报告。

将实际可见 DOM 取证写为调用方目录外的临时 JSON，再使用新的输出目录导入：

```bash
python3 <本 skill>/scripts/extract_note.py '<原链接>' '<新的 OUTPUT_DIR>' --rendered-note '<取证 JSON>'
```

取证包形状：

```json
{
  "schema": "feipi-xiaohongshu-rendered-note-v1",
  "source_url": "https://www.xiaohongshu.com/explore/0123456789abcdef01234567",
  "note": {
    "noteId": "0123456789abcdef01234567",
    "type": "normal",
    "title": "实际可见标题",
    "desc": "实际可见正文（含换行）",
    "user": {"nickname": "实际可见作者"},
    "timeDisplay": "页面日期显示原文；不可见则省略",
    "imageList": [{"url": "https://sns-webpic-qc.xhscdn.com/实际图片路径"}]
  }
}
```

- `type=normal` 为图文，`type=video` 为视频，必须依据实际轮播或视频元素判断。作者/日期不可获得时省略，不从笔记 ID 推算发布日期。相对日期只保存 timeDisplay，不伪装精确 published_at。
- `desc` 缺失表示没读到正文；明确看到空正文才传空字符串。页面标题与介绍不作为视频转写。
- 图片按实际轮播顺序填 imageList，只包括笔记图片；排除头像、评论图标和轮播克隆项。XHS 当前常见 `.note-container .swiper-slide:not(.swiper-slide-duplicate) .note-slider-img img`，逐图核验图号/总数与 `src`，懒加载图先正常翻到该页。选择器只是当前页面示例，结构变化时重新检查可见 DOM，禁止无证据猜测图序。
- 不把封面或 CSS 背景放进 frames。视频 `blob:` 地址不可交给 ffmpeg；可用浏览器 pageAssets 列表中实际已观察到的 http(s) 视频资源，不下载整个媒体。只有验证是当前笔记的资源时，额外添加 `video: {"url":"https://…xhscdn.com/…", "duration":373.45}`；duration 读取 video 元素显示/时长，不猜测。导入器会验证资源域名、Range/HLS 与采样时间。
- 脚本严格校验 source_url、原链接解析 ID 与 noteId 一致，来源标记 browser_dom；此包是宿主取证输入，脚本不会伪装成匿名页面解析。不要把全浏览器状态或任意页面对象序列化进包。

导入后仍需实际打开保存的每张图/帧，再登记 OCR/视觉观察。图片本身可能包含营销自述，摘要使用“文案称”“图上标注”等来源表述；商品参数、认证和功效不能自动视为核验事实。
