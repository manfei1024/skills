# 错误处置

## 判断成功与失败

- 同步接口的传输状态码**固定 HTTP 200**，成功与否看响应体 `code`：数字 `0` = 成功，字符串 = 错误码。**不要靠 HTTP 状态码判断。**
- 异步任务的失败通过轮询结果里的 `data.error_code` + `data.error_message` 返回。

## 处置总则

| 处置 | 含义 |
|---|---|
| **重试** | 退避后重试（30s / 60s / 120s，最多 3 次） |
| **停** | 不重试，如实告诉用户并给出下一步 |
| **改参数** | 回到参数构造，改完再提交（注意：这是一次新的扣费） |
| **转人工** | 需要用户去控制台操作，agent 做不了 |

**任何情况下都不要"换个参数偷偷再试一次"。** 每次提交都扣费，重试必须让用户知情。

## 鉴权与权限

| code | 处置 | 说明 |
|---|---|---|
| `Unauthorized` | 停 | 凭证无效/过期/停用。让用户去控制台重置 API Key |
| `Forbidden` | 停 | 三种可能：① 碰了 `/api/user/**`、`/api/team/**`、`/api/admin/**` 控制台专属域 → 转人工；② 密钥代表的成员角色不足；③ 账单接口要求团队 Owner。**都不要重试** |

## 计费

| code | 处置 | 说明 |
|---|---|---|
| `InsufficientBalance` | 停 | 积分不足。让用户去控制台充值。把「已完成/未提交」的分界说清楚，确认状态文件已记录，好让他充值后续跑 |
| `QuotaExceeded.MemberMonthlyCredits` | 停 | 团队管理员设的月度上限已用完。**充值解决不了**，要找管理员调额度 |
| `QuotaExceeded.ReviewAssetLibrary` | 停 | 审核素材库容量满。先清理旧的审核素材再提交，见 [click-assets](../skills/click-assets/SKILL.md) |

## 参数

| code | 处置 | 说明 |
|---|---|---|
| `MissingParameter.{X}` | 改参数 | 缺必填项。`{X}` 是参数名的 PascalCase |
| `InvalidParameter.Model` | 改参数 | 模型不受支持/未启用/类型不对。**重新查 model-list**，不要猜 |
| `InvalidParameter.ImageResolution` / `.VideoResolution` | 改参数 | 分辨率缺失、不受支持，或该模型压根不接受这个字段（`model_list.resolution` 为空数组时必须省略） |
| `InvalidParameter.AspectRatio` | 改参数 | 画幅不在该模型的 `aspect_ratio` 里；空数组时必须省略 |
| `InvalidParameter.Duration` | 改参数 | 时长超出 `model_list.duration` 的 `{min,max}` |
| `InvalidParameter.ReferenceImages` | 改参数 | 参考图数量超 `max_reference_images`、模式不匹配、URL/Base64 格式不对，或 `<imageN>` 占位符不合法 |
| `InvalidRequest.Body` | 改参数 | JSON 有未知字段或类型错误；图片接口请求体超 16 MiB 时 HTTP 返回 413 |
| `ResourceNotFound` / `ResourceNotFound.{X}` | 停 | 指定的项目/文件夹/资产/任务不存在或不属于当前团队。**先查状态文件是不是记了过期的 ID** |

## 上游生成服务

| code | 处置 | 说明 |
|---|---|---|
| `UpstreamError.RateLimited` | **重试** | 上游限流/并发/排队达限。这是唯一值得自动重试的一类 |
| `UpstreamError.ProviderUnavailable` | 重试一次 | 服务或网络不可用。仍失败就报给用户 |
| `UpstreamError.InvalidResponse` | 重试一次 | 上游响应无效或完成后没有产物 |
| `UpstreamError.ContentRejected` | 停 | 内容被安全策略拒（含版权和真人素材限制）。告诉用户是**哪一步、哪段提示词或哪张素材**被拒，建议改写或换素材。**不要自动改提示词重试** |
| `UpstreamError.InvalidRequest` | 改参数 | 上游判定参数或素材无效 |
| `UpstreamError.RequestRejected` | 停 | 上游业务拒绝但原因无法细分 |
| `UpstreamError.PromptTooLong` | 改参数 | 提示词超模型上限（Kling 系列 2500 字符，MiniMax-H3 7000） |
| `UpstreamError.ReferenceImageRequired` | 改参数 | 该模型必须带参考图 |
| `UpstreamError.ReferenceAssetExpired` | 改参数 | 参考素材已失效，重新上传 |
| `UpstreamError.ReferenceFileTooLarge` | 改参数 | 参考文件过大，压缩或更换 |
| `UpstreamError.ReferenceAudioRequiresVisual` | 改参数 | 用参考音频时必须同时带至少一张图或一段视频 |
| `UpstreamError.ReferenceAssetChannelMismatch` | 改参数 | 多个参考素材绑到了不同上游渠道，换成同一来源的 |

## 上传与媒体

| code | 处置 | 说明 |
|---|---|---|
| `Upload.UnsupportedFormat` | 停 | 文件为空/损坏/截断，或扩展名与实际内容不符，或是 HTML/SVG/JS/SWF 等主动内容。**平台按实际内容校验，改扩展名没用** |
| `Upload.Failed` | 重试 | 平台存储写入失败 |
| `MediaProcessing.Failed` | 重试一次 | 裁剪/合成/抽帧失败 |
| `InvalidResourceState.MediaAsset` | 停 | 素材还在生成中就被拿去删除/下载。等它到终态 |

## 短剧工作流

| code | 处置 | 说明 |
|---|---|---|
| `Storyboard.ScriptRequired` | 停 | 还没有剧本就去提取资产。先存剧本 |
| `Storyboard.ScriptGenerationInProgress` | 等待 | 已有剧本生成任务在跑且参数不一致。**等它跑完，不要再提交** |
| `Storyboard.ScenesRequired` | 停 | 剧本里没有场景就去建分镜项目 |
| `InvalidResourceState.StoryboardAsset` | 等待 | 资产参考图还在生成/同步。等全部到终态再建分镜项目或启动一键生成 |
| `InvalidResourceState.AutoProduceProject` | 停 | 一键项目正在运行，或目标是固定输出目录。**运行中不能改目录/产物** |

## 分镜

| code | 处置 | 说明 |
|---|---|---|
| `Shot.ShotsRequired` | 停 | 该场景/分集还没有镜头 |
| `Shot.GenerationInProgress` | 等待 | 该分镜项目或场景有活动任务，会冲突。等完成 |
| `Shot.ImportPreviewExpired` | 重做 preview | 文件指纹或目标场景在 preview 之后变了。**重新 preview，把新 diff 再给用户确认一遍**，不能拿旧的 `fingerprint` 硬 apply |

## 分集视频

| code | 处置 | 说明 |
|---|---|---|
| `EpisodeVideo.BatchGenerationInProgress` | 等待 | 该分集有批量任务在跑，此时不能移动片段顺序或再次自动分片 |
| `EpisodeVideo.ContinuitySourceRequired` | 停 | 片段配了引用上一片段尾帧，但上一片段还没有可用视频。先生成上一片段，或取消连续性引用 |
| `EpisodeVideo.SegmentDurationOutOfRange` | 改参数 | 自动分段后的片段时长超出模型 `duration` 范围。调分镜时长或换模型 |
| `InvalidResourceState.EpisodeVideo` | 停 | 没有片段、或还没有生成成功的片段视频就去导出 |

## 兜底

| code | 处置 | 说明 |
|---|---|---|
| `InternalError` | 重试一次 | 平台内部错误。仍失败就报给用户，附上做的是哪一步 |
| `RequestTimeout` | 重试 | 等待中的操作超时 |
| `RateLimited` | 重试 | 平台本地频率限制（注意与 `UpstreamError.RateLimited` 不同） |

## 报错给用户怎么说

不要贴原始 JSON，不要念错误码。说：**哪一步失败了 + 为什么 + 下一步做什么。**

> ❌ "任务失败，error_code: UpstreamError.ContentRejected"
>
> ✅ "第 2 条视频没通过内容审核——提示词里『持刀对峙』这类描述容易被拒。改成『紧张对视』我再试一次？这次会再扣约 2080 积分。"
