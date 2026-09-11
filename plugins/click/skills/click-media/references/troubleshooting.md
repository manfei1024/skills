# 图片 / 视频常见问题

通用错误码 → [errors.md](../../../common/errors.md)。这里只记单次生成特有的坑。

## 字段名

**视频用 `aspect`，图片用 `aspect_ratio`。** 两个接口不一样，最常见的错。

**`audio_list` 是裸 URL 数组**（`["https://…"]`），不是 `[{"url":"…"}]`。`image_list` 和 `video_list` 才是对象数组。

**图片和视频都返回 `data.id`**（短剧里的 `generate-image` 才是 `data.taskId`）。

## 分辨率 / 画幅报错

`InvalidParameter.VideoResolution` / `InvalidParameter.AspectRatio`：

三种情况，先查 model-list：

1. 值不在模型的数组里 → 换一个数组里的值
2. **模型的数组是空的 → 字段必须完全省略**，传了就错
3. 模型 `aspect_ratio` 为空数组时，`resolution` 要用**绝对尺寸**（如 `720x1280`）不是档位

MiniMax-H3 的分辨率是 `2k` / `768p`，大小写不敏感，和别的模型不一样。

## `InvalidParameter.Model`

model-list 里没有该模型的 active 行 = 不支持。**重新查 model-list，不要凭记忆。** 模型会上下线、改名。

## HTTP 413

图片接口整个 JSON 请求体（含 Base64）上限 **16 MiB**。

解法：把图先 `POST /api/upload` 传上去拿 URL，用 URL 代替 Base64。见 [upload.md](../../../common/upload.md)。

## 参考素材

**`InvalidParameter.ReferenceImages`** —— 数量超 `max_reference_images`，或形态不对（MiniMax-H3 图生要 1 张、首尾帧要 1 first + 1 end）。

**`InvalidParameter.VideoList`** —— 模型不支持参考视频、数量超限、或 `refer_type`/`keep_original_sound` 枚举无效（这两个字段**仅 kling-v3-omni**）。

**`InvalidParameter.AudioList`** —— 模型不支持参考音频，或 MiniMax-H3 多模态只给了音频没给图/视频。

**`UpstreamError.ReferenceAssetChannelMismatch`** —— 多个参考素材来自不同上游渠道。换成同一来源的。

参考视频硬限制：MP4/MOV、≤200 MB、≥3 秒、宽高 720–2160 px。

## 参考视频和首尾帧冲突

`video_list[].refer_type=base`（待编辑视频，**默认值**）时**不能定义首尾帧**。要配首尾帧就把 `refer_type` 设成 `feature`。

## `InvalidParameter.Watermark` / `AutoCreateAssets`

`watermark` 和 `auto_create_assets` **仅 seedance 支持**，其他模型传了就报错。不确定就别传。

## 多镜头

`shots` **仅 kling-v3 / kling-v3-omni**，最多 6 个。

`InvalidParameter.Shots` 的常见原因：

- **各镜 `duration` 之和 ≠ 顶层 `duration`** ← 最常见
- `index` 缺失、小于 1、或重复
- 单镜 `prompt` 为空或超 512 字符

kling-v3-omni 传了 `shots` 时可以省略顶层 `prompt`；**没传 `shots` 就必须有 `prompt`**。

## `MissingParameter.Prompt`

MiniMax-H3 **所有模式**都要 `prompt`。kling-v3-omni 未传 `shots` 时也要。图片接口 `prompt` 恒必填且去空白后不能为空。

## `UpstreamError.PromptTooLong`

Kling 系列 2500 字符，MiniMax-H3 7000，单个 shot 512。都是 **Unicode 字符数**不是字节数。

## `UpstreamError.ContentRejected`

提示词或素材没过内容审核。**不要自动改词重试**——告诉用户是哪段被拒，给改写建议，让他决定。每次重试都是一次新扣费。

## 需要审核素材库

model-list 里 `review_asset_enabled=true` 的模型，参考素材要先过 `POST /api/review-assets`。见 [click-assets](../../click-assets/SKILL.md)。

例外：seedance 传 `auto_create_assets=true` 时，参考素材由生成服务临时创建审核、用完清理，**不占审核素材库额度**。

## 任务提交了想取消

**没有中止接口。** 提交即不可撤销，扣费也退不回来。如实告诉用户，等结果出来再决定用不用。**不要假装取消了。**

## 会话断了

**不要重新提交。** 旧任务还在跑、还会扣费。查状态文件中该操作记录的 `poll_path` 补终态；单图/单视频通常是 `GET /api/ai/tasks/{task_id}`，不要把这条规则误套到其他任务类型。

## 要多张 / 多条

图片和视频接口都是**一次请求一个产物**。要 N 个就发 N 个请求、扣 N 次费。

批量之前：把总数和总价念给用户；先跑一个看效果再放量；同时在跑的不超过 3 个（并发上限未公开，遇 `UpstreamError.RateLimited` 退避重试 30/60/120s）。
