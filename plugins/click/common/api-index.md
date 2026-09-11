# 接口索引

按 Click 已发布的单接口文档页逐条核对而来。若在别处（旧版本、缓存、二手整理）看到与本表冲突的接口清单，**以单接口文档页为准**。

约定：
- Base URL = `${CLICK_HOST:-https://click.vibehub.art}`
- 除注明外都需要 `Authorization: Bearer $CLICK_API_KEY`
- `{}` = 路径参数
- **💰** = 会扣积分

---

## 通用

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/ai/model-list` | 模型能力与价格。**无需鉴权**。`?model_type=image\|video\|llm\|audio` |
| GET | `/api/quotas` | 审核素材库容量上限。**不是钱包余额**，无查询参数 |
| GET | `/api/auth/me` | 验证凭证身份。开工第一条 |
| POST | `/api/prompts/generate` | 提示词润色（同步）。`type` / `input` |
| GET | `/api/ai/tasks/{task_id}` | **统一任务轮询**（图/视频/音频/文本） |

## 上传

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/upload` | multipart，返回 `data.url` |
| POST | `/api/upload/process-video` | 远程视频裁剪转存，`videoUrl`/`startTime`/`endTime` |

## 单次生成（click-media）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ai/image/task` | 💰 必填 `model`/`prompt`/`aspect_ratio`；`resolution` 条件必填。请求体 ≤16 MiB 否则 HTTP 413 |
| POST | `/api/ai/video/task` | 💰 必填 `model`/`resolution`/`duration`；`aspect` 条件必填 |

两者都返回 `data.id`，用 `GET /api/ai/tasks/{task_id}` 轮询。

## 素材库（click-assets）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/folders/timeline` | 时间线视图 |
| GET | `/api/folders/contents` | 文件夹内容 |
| GET | `/api/folders/search` | 搜索 |
| GET | `/api/folders/ancestors` | 祖先链（面包屑） |
| GET | `/api/folders/delete-impact` | **删除前必查**：检查目录绑定项目；不覆盖全部素材级引用 |
| POST | `/api/folders` | 建文件夹 |
| POST | `/api/folders/move` | 移动 |
| PUT | `/api/folders` | 重命名/改属性 |
| DELETE | `/api/folders` | 删除（级联子树，不可撤销） |
| POST | `/api/media` | 可选：把已有 URL 登记为素材；平台上传用 `source=uploaded`，外部 URL 用 `source=imported` |
| GET | `/api/media/{id}` | 素材详情 |

全部不扣费。

## 审核素材库（click-assets）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/review-assets` | 提交预审核。不扣费但占配额 |
| GET | `/api/review-assets` | 列表 |
| GET | `/api/review-assets/{id}` | 详情 |
| DELETE | `/api/review-assets/{id}` | 删除，释放配额 |

触发条件：`model-list` 里该模型 `review_asset_enabled=true`。

---

## 短剧（click-drama）

### 项目

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/storyboards` | 项目列表 |
| POST | `/api/storyboards` | 建项目 |
| GET | `/api/storyboards/{id}` | 项目详情（含 assets、`asset_group_id`） |
| PUT | `/api/storyboards/{id}` | 改项目 |
| DELETE | `/api/storyboards/{id}` | 删项目 |
| POST | `/api/storyboards/quick-start` | 💰 灵感页一键建项目 |
| POST | `/api/storyboards/auto-produce` | 💰 **一键全链路**。必填 `prompt`/`flow_type`/`image_model`/`image_resolution`/`video_model`/`video_resolution` |
| GET | `/api/storyboards/auto-produce?id={pipeline_id}` | 一键链路状态。**查询参数不是路径参数** |
| GET | `/api/shorts` | 短片列表 |

`current_stage` ∈ `script` / `asset_images` / `shots` / `video` / `export` / `done`。

### 剧本

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/storyboards/{id}/generate-outline` | 生成大纲 |
| POST | `/api/storyboards/{id}/generate-script` | 生成剧本 |
| GET | `/api/storyboards/{id}/script` | 读剧本 |
| POST | `/api/storyboards/{id}/script` | **存剧本（POST 不是 PUT）** |
| PUT | `/api/storyboards/{id}/script/meta` | 改剧本元信息 |
| POST | `/api/storyboards/{id}/polish-scene` | 润色单场 |
| DELETE | `/api/storyboards/{id}/episodes/{episode_id}` | 删分集 |
| DELETE | `/api/storyboards/{id}/scenes/{scene_id}` | 删场景 |

### 资产（人物 / 场景参考图）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/storyboards/{id}/extract-assets` | **同步且不落库**，只返候选 `{kind,name,description,prompt}`，无 ID |
| GET | `/api/storyboards/{id}/assets` | 资产列表 |
| POST | `/api/storyboards/{id}/assets` | 落库拿 ID |
| POST | `/api/storyboards/{id}/assets/{asset_id}` | 改资产 |
| DELETE | `/api/storyboards/{id}/assets/{asset_id}` | 删资产 |
| POST | `/api/storyboards/{id}/assets/{asset_id}/generate-image` | 💰 **1 请求 = 1 张 = 计 1 次费**。要 16 张就发 16 个请求 |

### 分镜

路径前缀统一 `/api/shots/storyboards/{storyboard_id}/projects`。

| 方法 | 路径（省略前缀） | 说明 |
|---|---|---|
| GET | `` | 分镜项目列表 |
| POST | `` | 建分镜项目 |
| GET | `/{id}` | 详情 |
| DELETE | `/{id}` | 删除 |
| POST | `/{id}/generate` | 💰 批量生成分镜 |
| POST | `/{id}/generate-scene-shot` | 💰 单场生成 |
| GET | `/{id}/scene-tasks` | 场景任务状态 |
| POST | `/{id}/scenes/{scene_id}/generate-grid` | 💰 单场分镜图 |
| DELETE | `/{id}/scenes/{scene_id}/grid` | 删分镜图 |
| POST | `/{id}/scenes/{scene_id}/shots` | 加镜头 |
| PUT | `/{id}/scenes/{scene_id}/shots` | 覆盖场景镜头 |
| PATCH | `/{id}/scenes/{scene_id}/shots/{shot_id}` | 改单个镜头 |
| DELETE | `/{id}/scenes/{scene_id}/shots/{shot_id}` | 删单个镜头 |
| POST | `/{id}/imports/preview` | **BLOCKING：导入必须先 preview，把 diff 给用户核对** |
| POST | `/{id}/imports/apply` | 应用导入 |
| GET | `/{id}/export` | 导出分镜表 |

`preview` 返回的 `fingerprint` 过期后 `apply` 会报 `Shot.ImportPreviewExpired` → 重新 preview 并重新让用户确认。

### 分集视频

路径前缀统一 `/api/storyboards/{id}/shot-projects/{shot_project_id}`。**别漏掉 `/shot-projects/{shot_project_id}/` 这一段。**

| 方法 | 路径（省略前缀） | 说明 |
|---|---|---|
| GET | `/episode-video-list` | 分集视频总览 |
| GET | `/episode-video-tasks` | 任务列表 |
| GET | `/episodes/{episode_id}/video-items` | 片段列表 |
| POST | `/episodes/{episode_id}/video-items` | 建片段 |
| POST | `/episodes/{episode_id}/video-items/{item_id}/update` | 改片段（POST 不是 PUT） |
| DELETE | `/episodes/{episode_id}/video-items/{item_id}` | 删片段 |
| POST | `/episodes/{episode_id}/video-items/{item_id}/move` | 调顺序 |
| GET | `/episodes/{episode_id}/video-items/{item_id}/history` | 历史版本 |
| POST | `/episodes/{episode_id}/video-items/{item_id}/quick-generate` | 💰 **单条试跑。批量前必做** |
| POST | `/episodes/{episode_id}/video-items/auto-generate-segments` | 💰 **批量出片**（`generate_video=true` + `model` 必填）。不是 `generate-videos` |
| POST | `/episodes/{episode_id}/video-items/export` | 导出成片，**异步**，返回 `data.task_id` |
| POST | `/episodes/{episode_id}/video-items/export-jianying-zip` | 导出剪映工程 zip，异步 |

两个导出返回的 `data.task_id` 就是一条媒体任务 ID，用 `GET /api/ai/tasks/{task_id}` 轮询，`status=completed` 时读 `data.url` 拿下载链接。导出本身不扣费。

### 账单（仅团队 Owner）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/billing/storyboards` | 短剧消耗列表 |
| GET | `/api/billing/storyboards/{id}/dimensions` | 四维度构成 |
| GET | `/api/storyboards/{id}/billing` | 单项目消耗汇总 |

非 Owner 调用返回 `Forbidden`，不是 bug，不要重试。

---

## 已知缺口

**并发上限与单次批量条数上限平台未公开。** 保守做法：同时在跑的生成任务不超过 3 个，遇 `UpstreamError.RateLimited` 退避重试。

## 不在本 skill 覆盖范围

有路由但无对外文档，**不要调用**：`POST /api/ai/audio/tts`、`GET /api/ai/audio/voices`、`POST /api/ai/llm/chat[/stream]`、`POST /api/ai/composition/compose`、全部 legacy `/api/ai/image/*/generate`、`/api/v1/canvas/**`（已废弃）。

广告版本（`/api/storyboards/{id}/ad-products`、`/ad-versions`）是独立业务线，本 skill 不覆盖。

## 触不到的接口

`/api/user/**`、`/api/team/**`、`/api/admin/**` 对 API Key 一律 `Forbidden`。这些要用户去控制台操作。
