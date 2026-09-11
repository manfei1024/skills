# 分步链路

每个阶段：**做什么 → curl → 扣不扣费 → 要不要停下来问用户**。

`$SB_ID` = 短剧项目 ID，`$SP_ID` = 分镜项目 ID，`$EP_ID` = 分集 ID，`$ITEM_ID` = 视频片段 ID。

每拿到一个资源 ID 就用 `state-set --resource` 写进状态文件；每次提交生成任务都用共享脚本的 `submit`，在返回控制权前记录 `operation_type` 和准确 `poll_path`。见 [async-tasks.md](../../../common/async-tasks.md#提交并立即记录)。

---

## 1. 建项目

不扣费。

```bash
curl -s -X POST "$CLICK_HOST/api/storyboards" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"夏日便利店"}'
```

`name` 必填，**1-20 字符**，首尾空白会被忽略。可选 `asset_group_id`（归档文件夹，不传 = 根目录）。

返回 `data.id` → `$SB_ID`。

## 2. 剧本

### 2a. 用户自己有剧本

`POST /api/storyboards/$SB_ID/script`（**POST，不是 PUT**。PUT 只用于 `/script/meta`）。

结构：

```json
{
  "script": {
    "episodes": [
      {
        "index": 1,
        "title": "第一集",
        "scenes": [
          {
            "code": "1-1",
            "heading": "内景-便利店-深夜",
            "beats": [
              { "kind": "action", "text": { "text": "店员趴在收银台睡着。" } },
              { "kind": "dialogue", "speaker": "顾客", "text": { "text": "有热的关东煮吗？" } }
            ]
          }
        ]
      }
    ]
  }
}
```

必填：`episodes[].index`（1-based）、`scenes[].code`、`scenes[].heading`、`beats[].kind`、`beats[].text.text`。

`kind` ∈ `action` / `dialogue` / `voiceover` / `wow` / `key` / `note`。`speaker` 一般配 `dialogue`。

`id` 留空由后端生成。`sceneAssetId` 和 `beats[].text.mentionIds` 用来绑资产，第一次存剧本时可以不填，资产落库拿到 ID 后再回来补。

**你的活儿在这里**：用户在对话里给的是自然语言剧本，把它转成这个结构是 agent 该做的事。转完把分集数、场数报给用户确认再存。

### 2b. 让平台生成

`POST /api/storyboards/$SB_ID/generate-outline`（大纲）、`POST /api/storyboards/$SB_ID/generate-script`（剧本）。

`GET /api/storyboards/$SB_ID/script` 读回来。`POST /api/storyboards/$SB_ID/polish-scene` 润色单场。

### ⏸ 检查点

把剧本梗概讲给用户听（几集、几场、主要人物），确认了再往下。**下一步开始花钱。**

## 3. 资产（角色 / 道具 / 场景）

### 3a. 提取候选

```bash
curl -s -X POST "$CLICK_HOST/api/storyboards/$SB_ID/extract-assets" \
  -H "Authorization: Bearer $CLICK_API_KEY"
```

**同步返回，不落库，无请求体。** 返回 `data.assets[]`，每项 `{kind, name, description, prompt}`，`kind` ∈ `role` / `prop` / `scene`。

剧本为空 → `Storyboard.ScriptRequired`。

### 3b. 落库

用户确认/增删后：

```bash
curl -s -X POST "$CLICK_HOST/api/storyboards/$SB_ID/assets" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"assets":[{"kind":"role","name":"林栖","description":"…","prompt":"…"}]}'
```

单条也用数组。返回 `data.ids[]`，**顺序与请求一致**——按顺序对上名字记进状态文件。

改已有资产用 `POST /api/storyboards/$SB_ID/assets/{asset_id}`（也是 POST）。

`referenceAssetIdList` 要的是 media_asset **ID**，不是 URL。本地参考图先调用 `POST /api/upload` 取得 URL，再以 `source=uploaded` 调用 `POST /api/media`，把返回的 `data.id` 填进列表。只上传文件不会创建可引用的素材记录。见 [upload.md](../../../common/upload.md#上传后登记到素材库)。

### 3c. 生成参考图 💰

**BLOCKING：一个请求固定生成一张、计一次费。** 有 12 个资产、每个要 2 张 = 24 次扣费。**批量前把总数和总价念给用户。**

```bash
curl -s -X POST "$CLICK_HOST/api/storyboards/$SB_ID/assets/$ASSET_ID/generate-image" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"<来自 model-list>","aspect_ratio":"9:16","resolution":"1K","auto_bind":true}'
```

| 参数 | 说明 |
|---|---|
| `model` | 必填，来自 model-list |
| `prompt` | 不传就用资产已有的 `prompt` |
| `aspect_ratio` / `resolution` | 取值必须在该模型的数组里 |
| `n` | 兼容字段，永远归一为 1。**别指望用它批量** |
| `auto_bind` | 缺省 `true` = 结果自动绑到资产 |
| `group_id` | 结果存哪个素材库文件夹 |
| `asset_name` | 存进素材库的名字，批量建议带 `(2/4)` 后缀 |

同一资产要多张时：**先提交 `auto_bind=true` 的主任务，受理后再提交 `auto_bind=false` 的其余任务。** 主任务失败就不要提额外任务。一个资产最多绑 4 张，绑满后主图也只进素材库。

返回 `data.taskId`（**camelCase**，和别处的 `data.id` / `data.task_id` 不一样）+ `data.status`。用 `GET /api/ai/tasks/{task_id}` 轮询。

同时在跑的不超过 3 个。

### ⏸ 检查点

把参考图给用户看。**不满意就在这里重生成——越往后改代价越大**（分镜和视频都基于这些图的形象）。

## 4. 分镜项目

```bash
curl -s -X POST "$CLICK_HOST/api/shots/storyboards/$SB_ID/projects" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"夏日便利店-分镜","instructions":"节奏紧凑，适合竖屏"}'
```

不扣费。所有参数都可选。

**⚠️ 返回 `data` 固定为 `null`，拿不到项目 ID。** POST 前后各取一次项目列表，计算 ID 集合差集。只有唯一新增项时才能作为 `$SP_ID`；新增为 0 或多于 1 时停止并让用户核对。**禁止按“最新一条”猜 ID。**

剧本没有场景 → `Storyboard.ScenesRequired`；资产图还在同步 → `InvalidResourceState.StoryboardAsset`（等，别重试轰它）。

## 5. 分镜：二选一

### 5a. 平台生成 💰

```bash
curl -s -X POST "$CLICK_HOST/api/shots/storyboards/$SB_ID/projects/$SP_ID/generate" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"instructions":"…","skip_storyboard_grid":false}'
```

`skip_storyboard_grid=true` = 只出分镜文本不出分镜图，**更省**。用户只想要文字分镜就传 true。

返回 `data.project_id`。`GET .../projects/$SP_ID/scene-tasks` 看场景级进度。

已有任务在跑 → `Shot.GenerationInProgress`，等它，别重复提交。

单场重生成：`POST .../projects/$SP_ID/generate-scene-shot`（💰）。单场分镜图：`POST .../projects/$SP_ID/scenes/{scene_id}/generate-grid`（💰）。

### 5b. 导入用户自己写的分镜

不扣费。见 **[shot-import.md](./shot-import.md)**。

### 手工编辑

`POST .../scenes/{scene_id}/shots` 加、`PUT .../scenes/{scene_id}/shots` 整场覆盖、`PATCH .../scenes/{scene_id}/shots/{shot_id}` 改单条、`DELETE` 删。都不扣费。

### ⏸ 检查点

把分镜表讲给用户（多少场、多少镜头、总时长感觉）。确认了再进视频阶段——**视频是最贵的**。

## 6. 视频片段

路径前缀：`/api/storyboards/$SB_ID/shot-projects/$SP_ID/episodes/$EP_ID`。**`/shot-projects/$SP_ID/` 这段别漏。**

### 6a. 建片段

```bash
curl -s -X POST "$CLICK_HOST/api/storyboards/$SB_ID/shot-projects/$SP_ID/episodes/$EP_ID/video-items" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"source_scene_id":"scene_xxx","shot_ids":["shot_1","shot_2"],"model":"<来自 model-list>","continuity_tail_frame_mode":"auto"}'
```

不扣费。`source_scene_id` 必填。`shot_ids` 不传 = 空壳片段；传了后端从选中分镜生成文稿和镜头列表。`model` 会存到片段供后续 `quick-generate` 用。

`continuity_tail_frame_mode: "auto"` = 让后端判断要不要接上一片段的尾帧。没有上一片段或判断失败就存 `none`。

返回 `data.item_id`。

### 6b. 单条试跑 💰（BLOCKING）

**批量之前必须先跑一条给用户看。** 这是防止"批量生成 20 条全是废片"的唯一手段——而且**没有中止接口**，批量跑起来就停不下来。

```bash
curl -s -X POST "$CLICK_HOST/api/storyboards/$SB_ID/shot-projects/$SP_ID/episodes/$EP_ID/video-items/$ITEM_ID/quick-generate" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"<来自 model-list>","resolution":"1080p","generate_audio":true}'
```

全部参数可选：`model` 不传用片段已存的；`provider` 不传按 model-list 解析；`resolution` 不传用模型默认档；`generate_audio` 不传默认开。

返回 `data.video_task.{id,status,url,thumbnail}` + `data.item` 快照。用 `data.video_task.id` 轮询。

`InvalidResourceState.*` = 片段文稿为空，或衔接依赖没满足（上一片段还没出视频 → `EpisodeVideo.ContinuitySourceRequired`）。

### ⏸ 检查点

把这条视频给用户看。**满意才批量。** 不满意就在这里调模型/分辨率/提示词——一条的代价远低于一整集。

### 6c. 批量出片 💰

```bash
curl -s -X POST "$CLICK_HOST/api/storyboards/$SB_ID/shot-projects/$SP_ID/episodes/$EP_ID/video-items/auto-generate-segments" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"replace_existing":false,"generate_video":true,"model":"<来自 model-list>","resolution":"1080p","generate_audio":true}'
```

**不是 `generate-videos`——那个接口不存在。**

| 参数 | 说明 |
|---|---|
| `model` | **必填**，`generate_video` 关着也要传。后端读它的时长上下限来分组打包分镜 |
| `generate_video` | 默认 `false` = 只切片段不出片。**想出片必须显式传 `true`** |
| `replace_existing` | 默认 `false` = 保留旧片段并追加。`true` = **删掉旧片段，旧视频跟着没**，提交前必须让用户确认 |
| `resolution` / `generate_audio` | 仅 `generate_video=true` 时生效 |

返回 `data.task_id`。`GET .../shot-projects/$SP_ID/episode-video-tasks` 看批量进度。

归一化后片段时长仍超模型范围 → `EpisodeVideo.SegmentDurationOutOfRange`：调分镜时长或换一个 `duration` 范围更宽的模型。

有任务在跑 → `EpisodeVideo.BatchGenerationInProgress`，等。

### 6d. 单条重做

某条不满意：改片段 `POST .../video-items/$ITEM_ID/update`，再 `quick-generate` 单跑一条（💰）。不要为一条重跑整批。

`GET .../video-items/$ITEM_ID/history` 看历史版本。`POST .../video-items/$ITEM_ID/move` 调顺序（批量任务跑着的时候不能调）。

## 7. 导出

```bash
curl -s -X POST "$CLICK_HOST/api/storyboards/$SB_ID/shot-projects/$SP_ID/episodes/$EP_ID/video-items/export" \
  -H "Authorization: Bearer $CLICK_API_KEY"
```

无请求体。返回 `data.task_id`（异步）。剪映工程包换成 `export-jianying-zip`。

没有已生成的片段视频 → `InvalidResourceState.EpisodeVideo`。

取下载链接见 [SKILL.md 的「取成片」](../SKILL.md#取成片)。

## 多集

每一集重复第 6-7 步，`$EP_ID` 换成对应分集。`GET .../shot-projects/$SP_ID/episode-video-list` 看全部分集状态。

**别多集并行猛跑**——并发上限未公开，保守不超过 3 个在跑的任务。
