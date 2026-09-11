---
name: click-assets
description: |
  管理 Click 素材库，以及视频生成前的合规预审核。不执行图片或视频生成；公开文档未给这些操作列出扣费错误码。
  触发场景："把这些素材整理到一个文件夹"、"新建个目录放角色图"、"素材库里找一下…"、
  "这几张图能过审吗"、"先把参考素材传上去"、"审核素材库满了帮我清一下"、"删掉这个文件夹"、
  "把这些文件移到…"、"传张图给我拿个 URL"。
  NOT for: 生成图片或视频 → click-media。做短剧 → click-drama。
  Chain signal: 素材传好/过审后要拿去生成 → click-media 或 click-drama。
---

# Click 素材管理

首先执行 [使用前版本检查](../../common/version-check.md)。这是 BLOCKING；确认当前版本最新后，才执行下文。

你是**素材管理员**。这个 skill 不执行生成；公开文档未给这些操作列出扣费错误码。删除是永久的，审核素材库有容量上限。

先读 [common/](../../common/) 下的共享规则：[auth.md](../../common/auth.md) · [upload.md](../../common/upload.md) · [errors.md](../../common/errors.md) · [models.md](../../common/models.md)

## 交流规则

- 不报内部 ID，不贴原始 JSON。说"传好了""建好了""这个文件夹里有 12 张图"。
- 不叙述内部动作。
- 跟用户说什么语言就用什么语言。

## 开工检查（BLOCKING）

`CLICK_HOST` 缺失就使用正式默认地址 `https://click.vibehub.art`；本地/私有部署才覆盖。`CLICK_API_KEY` 缺失就让用户在环境中配置，不要让他贴进对话。跑 `GET /api/auth/me` 验，`Unauthorized` 就停。

---

## 上传

见 [upload.md](../../common/upload.md)。要点：`POST /api/upload`（multipart）只把文件传到存储并返回 `data.url`，**不会创建素材记录**；按实际内容校验，改扩展名没用；HTML/SVG/JS/SWF 一律拒。

生成接口只需要 URL。用户只是要拿本地文件生成时，上传后直接使用 `data.url`，不要多建素材记录。

用户明确说“上传到素材库”“作为素材管理”，或下游需要 media_asset ID 时，上传成功后再登记：

```bash
curl -s -X POST "$CLICK_HOST/api/media" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type":"image","name":"角色参考图.png","source":"uploaded","url":"<data.url>","group_id":"root"}'
```

`type` 按实际素材传 `image` / `video` / `audio` / `text` / `file`；登记本次上传返回的 URL 时，`source` 固定为 `uploaded`。返回的 `data.id` 是短剧 `referenceAssetIdList` 使用的 media_asset ID。生成接口仍引用上传返回的 URL。

外部公网 URL 也能登记，但平台只保存引用，不复制文件、不证明所有权。只有用户明确要求管理该外链时才用 `source=imported` 登记，并提醒外部内容可能变化或失效。不要把任意外部 URL 标成 `uploaded`。平台会在登记前做 SSRF 安全的限量内容探测和实际类型校验。

远程视频要裁一段：`POST /api/upload/process-video`。

## 素材库

全部不扣费。`root` 是虚拟根目录的固定 ID。

### 浏览

```bash
# 某个文件夹里有什么
curl -s "$CLICK_HOST/api/folders/contents?parent_id=root&page=1&page_size=40" \
  -H "Authorization: Bearer $CLICK_API_KEY"
```

| 接口 | 用途 |
|---|---|
| `GET /api/folders/contents` | 直接子内容。`parent_id` **必填**（`root` = 根目录） |
| `GET /api/folders/timeline` | 按更新时间倒序列全部素材（不分目录） |
| `GET /api/folders/search` | 按名称模糊搜。`parent_id` 限定子树，默认 `root` |
| `GET /api/folders/ancestors?folder_id=…` | 面包屑；数组第一项永远是根目录（`id="root"`，`name=""`） |
| `GET /api/media/{id}` | 单个素材详情：`url`、`prompt`、`model`、`status`、`content` |

公共查询参数：`type`（**多选靠重复传参**：`?type=folder&type=image`；枚举 `folder`/`image`/`video`/`audio`/`text`，timeline 不含 `folder`/`text`）、`sort`（`name`/`created_at`/`updated_at`，默认 `updated_at`）、`order`（`asc`/`desc`，默认 `desc`）、`page`、`page_size`（默认 40，**最大 100**）。

**文件夹永远排在素材前面**，两组各自排序后统一分页。

`updated_at` 是**用户修改时间**——只在改名、改标签、移动、保存编辑后才前移；**生成任务的状态流转不改它**。别拿它判断"生成完了没"。

搜索结果里文件夹有 `path`（完整路径），素材有 `group_id`（所属文件夹，根目录素材返回 `root`）。

### 建 / 改名 / 移动

```bash
curl -s -X POST "$CLICK_HOST/api/folders" \
  -H "Authorization: Bearer $CLICK_API_KEY" -H "Content-Type: application/json" \
  -d '{"name":"角色图片","parent_id":"root"}'
```

`name` 和 `parent_id` 都必填。返回 `data.id`。

**名称规则**：1-100 字符，只允许中英文数字 + `:` `_` `.` 空格 `-`。同级不能重名（`InvalidResourceState.*`）。

改名 `PUT /api/folders`：`{"folder_id":"…","name":"…"}`。**`root` 不能改名。**

移动 `POST /api/folders/move`：

```json
{"folder_ids":["folder-a"],"asset_ids":["asset-b"],"target_folder_id":"folder-target"}
```

`folder_ids` / `asset_ids` **至少给一个非空**，`target_folder_id` 必填（`root` = 移到根目录）。

**原子操作**——任一目标动不了，整批不执行。文件夹移动保留整棵子树、素材和短剧绑定；素材移动只改所属文件夹，不复制、不清引用。

`InvalidParameter.TargetFolderID` 常见原因：目标不存在、想移动 `root`、源文件夹互相包含、会形成循环层级。

### 删除（BLOCKING）

**永久，级联整棵子树。做之前必须先查影响。**

```bash
curl -s "$CLICK_HOST/api/folders/delete-impact?folder_id=folder-a&folder_id=folder-b" \
  -H "Authorization: Bearer $CLICK_API_KEY"
```

`folder_id` 必填，可重复传多个。**`root` 不能和普通 ID 混传**（`InvalidRequest.Body`）。

返回 `data.storyboards[]`：仍绑定在这些目录上的短剧项目（`id` / `name` / `asset_group_id`）。

**检查盲区：**这个接口只检查“目录绑定”，不保证发现素材级引用。只引用了目录内素材、但项目绑定在其他目录的短剧不会返回；单独删除 `asset_ids` 也没有完整的引用影响反查。因此：

- `data.storyboards` 为空只能说“未发现绑定到这些目录的短剧”，**不能说“删除没有影响”**；
- 删除任何单独素材或非空目录前，列出将删除的文件夹/素材数量和名称，说明可能存在无法检测的素材引用，再取得明确确认；
- 返回非空时，还要逐个念出已发现的项目；不能用已发现列表代表完整影响范围。

**无论结果是否为空都要明确确认；结果非空时逐个念出已发现项目。**

```bash
curl -s -X DELETE "$CLICK_HOST/api/folders" \
  -H "Authorization: Bearer $CLICK_API_KEY" -H "Content-Type: application/json" \
  -d '{"folder_ids":["folder-a"],"asset_ids":["asset-b"]}'
```

`{"folder_ids":["root"]}` = **清空整个根目录**。这个必须重复确认，且 `root` 不能与其他目标混传。

| code | 含义 |
|---|---|
| `InvalidResourceState.FolderWithStoryboards` | 文件夹或子文件夹还绑着短剧。**得先逐个删短剧**，删不了目录 |
| `InvalidResourceState.AutoProduceProject` | 一键项目在跑，或是它的固定输出目录，不许删/移/改名 |
| `InvalidResourceState.MediaAsset` | 素材还在生成中，等到终态再删 |

---

## 审核素材库

和素材库是**两套东西**，独立的表。用途：某些视频模型要求参考素材先过合规审核。

**不扣积分，但有容量上限。**

### 什么时候需要

查 model-list，该模型 `review_asset_enabled=true` 就需要。见 [models.md](../../common/models.md)。

**例外**：seedance 走 `POST /api/ai/video/task` 且传 `auto_create_assets=true` 时，参考素材由生成服务临时创建审核、用完清理，**不进素材库也不占审核配额**。这条能省事就用。

### 查容量

```bash
curl -s "$CLICK_HOST/api/quotas" -H "Authorization: Bearer $CLICK_API_KEY"
```

无查询参数。返回 `data.list[]`，每项 `{type:"review_asset_library", model, limit}`——**按模型分别限额**。

**这不是钱包余额。** 平台没有查余额的接口。

### 流程

见 **[references/review-flow.md](references/review-flow.md)**。骨架：

```
POST /api/upload 拿公网 URL
  → POST /api/review-assets 提交（拿 data.id）
  → 轮询 GET /api/review-assets/{id} 直到 approved / failed
  → approved 才能用于该模型的视频生成
```

状态：`pending` → `reviewing` → `approved` / `failed`。

### 清理

```bash
curl -s -X DELETE "$CLICK_HOST/api/review-assets/$ID" -H "Authorization: Bearer $CLICK_API_KEY"
```

**只有终态（`approved` / `failed`）能删**，`pending` / `reviewing` 删会被拒。异步受理，返回 `data: null`。

配额满（`QuotaExceeded.ReviewAssetLibrary`）→ `GET /api/review-assets?model=…` 列出来，挑 `failed` 的和用不上的删掉。

---

## 三个容易混的字段

`image_list[].url`（**输入 URL**） / `referenceAssetIdList`（**输入 media_asset ID**） / `group_id`（**输出归档文件夹**）。语义完全不同，不能互换。见 [upload.md](../../common/upload.md#三个容易混的字段)。

## 接下来

素材准备好了要生成 → [click-media](../click-media/SKILL.md)（单张图/单条视频）或 [click-drama](../click-drama/SKILL.md)（整部短剧）。
