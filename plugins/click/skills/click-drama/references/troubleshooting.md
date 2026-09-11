# 短剧常见问题

通用错误码 → 处置见 [errors.md](../../../common/errors.md)。这里只记短剧特有的坑。

## 路径

**分集视频的路径少了一段。** 正确前缀是 `/api/storyboards/{id}/shot-projects/{shot_project_id}/episodes/{episode_id}/…`，漏掉 `/shot-projects/{shot_project_id}/` 会 404 或 `MissingParameter.ProjectID`。

**`GET /api/storyboards/auto-produce?id=…` 是查询参数**，不是 `/api/storyboards/{id}/auto-produce`。

**存剧本是 POST 不是 PUT。** PUT 只用于 `/script/meta`。

**改片段是 `POST .../video-items/{item_id}/update`**，不是 PUT。

**改资产是 `POST .../assets/{asset_id}`**，不是 PUT。

## 返回字段不统一

| 接口 | 任务 ID 字段 |
|---|---|
| `generate-image` | `data.taskId`（camelCase） |
| `quick-generate` | `data.video_task.id` |
| `auto-generate-segments` / `export` | `data.task_id` |
| `/api/ai/image/task`、`/api/ai/video/task` | `data.id` |

按接口取，别统一猜。

## 建分镜项目拿不到 ID

`POST /api/shots/storyboards/{sid}/projects` 的 `data` **固定为 `null`**。POST 前后分别列出项目，取唯一新增 ID；差集不是恰好一项就停止。不要按“最新一条”猜。

## 提取资产之后没有 ID

`extract-assets` **只返回候选，不落库**。返回项里没有 `id` 是设计如此。必须再 `POST /api/storyboards/{id}/assets` 才拿得到 `data.ids[]`。

## 参考图只出一张

`n` 是兼容字段，**永远归一为 1**。要 N 张就发 N 个请求，扣 N 次费。先发一个 `auto_bind=true` 的主任务，受理后再发 `auto_bind=false` 的其余任务。一个资产最多绑 4 张。

## 批量出片没出视频

`auto-generate-segments` 的 `generate_video` **默认 `false`**，只切片段不出片。想出片必须显式传 `true`。

`model` **无论如何都必填**，哪怕 `generate_video=false`——后端要读它的时长范围来打包分镜。

## 批量把之前的视频弄没了

`replace_existing=true` 会**删掉旧片段，旧片段上的视频一起没**。默认 `false`（保留并追加）。传 `true` 前必须让用户确认。

`episode-video-list` 返回 `has_unknown_source_items=true` 时通常需要替换。

## 卡在「资产图尚未同步完成」

`InvalidResourceState.StoryboardAsset` 或建分镜项目报 `MissingParameter.*` / `InvalidParameter.*` 且提示资产图未同步。

参考图生成任务还没到终态。**等**，逐个查 `GET /api/ai/tasks/{task_id}` 确认全部 `completed` 或 `failed` 再往下。别反复重试轰接口。

## 片段时长超模型范围

`EpisodeVideo.SegmentDurationOutOfRange`。后端按模型 `duration` 上限打包分镜、归一化超限单镜（如 16 秒归到 15 秒），但**下限不做归一**——归一后仍低于下限就报错。

解法：调分镜时长，或换 `duration` 范围更宽的模型（查 model-list）。

## 连续性依赖

`EpisodeVideo.ContinuitySourceRequired`：片段配了引用上一片段尾帧，但上一片段还没有可用视频。

**按顺序生成**，或把该片段的 `continuity_tail_frame_mode` 改成 `none`。

## 生成中冲突

- `Shot.GenerationInProgress` —— 分镜项目/场景有活动任务
- `EpisodeVideo.BatchGenerationInProgress` —— 分集有批量任务；此时不能移动片段顺序、不能再次自动分片
- `Storyboard.ScriptGenerationInProgress` —— 剧本生成任务在跑

**都是等，不是重试。** 平台没有 stop 接口，重复提交只会多扣钱。

## 一键链路中途想改

改不了。`auto-produce` 启动后只能观测。这句话要在**提交前**说，不是跑起来才说。

用户坚持要停 → 如实说：任务无法中止，积分已扣，只能等它跑完再决定用不用。**不要假装取消了。**

## 会话断了

**先找 `CLICK-*.json`，不要新建项目。**

1. 读状态文件拿各级 ID
2. 「已提交未完成的任务」逐个查 `GET /api/ai/tasks/{task_id}` 补终态
3. 从「当前阶段」往后接着做

一键链路：`GET /api/storyboards/auto-produce?id=$PIPELINE_ID` 一条就知道跑到哪了。

**重头再来 = 重复扣费，而且旧任务停不掉。**

## 导出后拿不到成片

导出任务和图片/视频任务是同一套：拿 `export` 返回的 `data.task_id` 去查 `GET /api/ai/tasks/{task_id}`，`status=completed` 时读 `data.url`。

还在 `pending` / `processing` 就是没导完，**等**。到 `failed` 看 `data.error_message`，导出不扣费，可以重新调一次 `export`。

**不要因为拿不到链接就重跑视频生成**——那才是扣费的那步。

## 账单看不了

`GET /api/billing/storyboards` 等**仅团队 Owner**。非 Owner 返回 `Forbidden`，不是 bug，不要重试。

## 生成质量不满意

按代价从小到大改：

1. **改提示词**（资产 prompt、分镜 instructions）—— 最便宜
2. **单条 `quick-generate` 重跑** —— 一条的钱
3. **换模型/分辨率** —— 先用一条试
4. **重生成参考图** —— 影响后续全部，但比重出视频便宜
5. **重跑批量** —— 最贵，做之前一定先单条验过

**永远先在最小粒度上验证，再放量。**
