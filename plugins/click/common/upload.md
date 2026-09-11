# 上传与素材引用

## 上传文件

```bash
curl -s -X POST "$CLICK_HOST/api/upload" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -F "file=@./ref.png" \
  -F "keyPrefix=images"
```

`multipart/form-data`。`file` 必填；`keyPrefix` 可选（如 `thumbnails` / `images` / `videos`），不传落 `uploads/`。

返回 `data.url`（CDN URL）、`data.hash`、`data.name`、`data.size`。**后续所有生成接口的参考素材，都用这个 `data.url`。**

没有预签名直传，只有这一条服务端转存。不扣费。

### 上传后登记到素材库

`POST /api/upload` **只上传文件，不创建素材库记录**。图片和视频生成只消费参考 URL，不查询对应的 media_asset；拿到 `data.url` 后已经可以生成。

`POST /api/media` 是**可选的管理步骤**。仅在用户明确要求把文件放进素材库、后续要按素材管理，或短剧 `referenceAssetIdList` 需要 media_asset ID 时调用：

```bash
curl -s -X POST "$CLICK_HOST/api/media" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type":"image",
    "name":"角色参考图.png",
    "source":"uploaded",
    "url":"<POST /api/upload 返回的 data.url>",
    "group_id":"root"
  }'
```

`type` ∈ `image` / `video` / `audio` / `text` / `file`；只有登记 `POST /api/upload` 刚返回的 URL 时才用 `source=uploaded`。`group_id` 可省略，省略时进入根目录。返回的 `data.id` 是 media_asset ID。

两条路径不要混在一起：

```text
仅生成：POST /api/upload 取得 data.url → 图片/视频生成使用 data.url

需要入库或 ID：POST /api/upload 取得 data.url
  → POST /api/media 创建素材记录，取得 data.id
  → 短剧 referenceAssetIdList 使用 data.id
```

生成接口的 `group_id` 只控制**生成结果**的保存位置，不会把输入参考素材登记到素材库。要把参考素材放进指定目录，在 `POST /api/media` 中传对应的 `group_id`。

### 外部 URL 入库

`POST /api/media` 不要求 URL 来自平台对象存储，也接受公网 HTTP(S) URL。平台会对外部 URL 做限量内容探测和素材类型校验，并拒绝用户凭证、私网、回环、链路本地地址和不安全重定向；但**不会证明外部文件的所有权，也不会把它复制到平台存储**。外部内容可能变化、失效或被撤回。

因此：

- 不要为了生成而自动登记外部参考 URL；生成接口直接使用 URL 即可。
- 只有用户明确要把外部文件作为素材管理时才登记，使用 `source=imported`，并说明这是外链引用。
- `source=uploaded` 只用于本次 `POST /api/upload` 返回的 URL，不要把任意外部 URL 伪装成上传素材。

### 支持的类型

- 图片 PNG / JPEG / WebP
- 视频 MP4 / MOV
- 音频 MP3 / WAV / M4A
- 文档 TXT / Markdown / JSON / CSV / YAML / PDF / DOC / DOCX

**明确拒绝**：HTML、XHTML、MHTML、SVG、JavaScript、SWF 等主动内容。

**按实际内容校验，不看扩展名。** 改后缀名绕不过去——用户拿一个 `.png` 后缀的 SVG 来，一样报 `Upload.UnsupportedFormat`。遇到这个错就直说文件格式不受支持，不要重试、不要建议改后缀。

限制：图片 2000 万像素；JSON 16 MiB；DOCX 解压校验 128 MiB。

## 视频裁剪转存

```bash
curl -s -X POST "$CLICK_HOST/api/upload/process-video" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"videoUrl":"https://…/v.mp4","startTime":"00:00:10","endTime":"00:00:30"}'
```

拿公网视频 URL，按需裁剪后转存，返回 `data.url`。不传 `startTime`/`endTime` 就只校验并原样返回原 URL。时间格式固定 `HH:MM:SS`。

用途：用户给了一段长视频但只想引用其中一段。

## 三个容易混的字段

这三个长得像，但语义完全不同，**不能互换**：

| 字段 | 是什么 | 用在哪 |
|---|---|---|
| `image_list[].url` / `video_list[]` / `audio_list[]` | **输入**：参考素材的 URL 字符串 | `POST /api/ai/image/task`、`POST /api/ai/video/task` |
| `referenceAssetIdList` | **输入**：参考图的 media_asset **ID 数组**（不是 URL） | 短剧资产：`POST /api/storyboards/{id}/assets`、`POST /api/storyboards/{id}/assets/{asset_id}` |
| `group_id` / `asset_group_id` | **输出**：结果存到哪个素材库文件夹 | 生成类接口、建项目接口 |

划重点：

- **`group_id` 不是参考素材。** 它只决定产物归档位置，传不传都不影响生成内容。不传或传 `root` = 素材库根目录。传了不存在的文件夹 → `ResourceNotFound`。
- **`referenceAssetIdList` 要 ID，不要 URL。** 这是少数必须登记素材的路径：上传本地文件后调用 `POST /api/media`，使用返回的 `data.id`（见 [click-assets](../skills/click-assets/SKILL.md)）。把 `POST /api/upload` 返回的 URL 塞进去必然失败。
- **`image_list[].url` 要 URL，不要 ID。** 反过来同理。

单条视频生成的 `image_list[]` 还有个 `role` 字段：`first_frame` / `end_frame` / `reference_image`。选哪个要和模型的 `gen_modes` 对上——`start_end_to_video` 才认首尾帧。见 [models.md](./models.md#gen_modes)。

## 审核素材库是另一回事

`model-list` 里 `review_asset_enabled=true` 的模型，参考素材必须先过审核素材库（`POST /api/review-assets`），不能直接给 URL。见 [click-assets](../skills/click-assets/SKILL.md)。
