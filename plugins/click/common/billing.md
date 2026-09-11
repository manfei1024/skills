# 计费

## 核心事实

1. **花的是团队的钱。** API Key 绑定团队主体，消费从团队账户扣，账单标记来源 `user_api_key`。
2. **没有查余额的对外接口。** 提交前无法预检，只能在提交时收到 `InsufficientBalance` 才知道不够。
3. **没有 stop 接口，扣了就扣了。** 提交即不可撤销。
4. **所以：提交前算预估 + 让用户确认，是唯一的防线。**

## `GET /api/quotas` 不是查余额

```bash
curl -s "$CLICK_HOST/api/quotas" -H "Authorization: Bearer $CLICK_API_KEY"
```

它返回的是**审核素材库的容量上限**，按模型维度：

```json
{"code":0,"data":{"list":[{"type":"review_asset_library","model":"seedance-2.0","limit":50}]}}
```

无查询参数。别把它当钱包用，也别用它判断某模型是否需要审核素材库——那个看 `model-list` 的 `review_asset_enabled`。

## 哪些调用扣费

判据：接口文档的返回码里列了 `InsufficientBalance` 就是扣费的。

**扣费**：

| 操作 | 接口 |
|---|---|
| 单张图片生成 | `POST /api/ai/image/task` |
| 单条视频生成 | `POST /api/ai/video/task` |
| 短剧一键全链路 | `POST /api/storyboards/auto-produce` |
| 灵感页一键建项目 | `POST /api/storyboards/quick-start` |
| 资产参考图生成 | `POST /api/storyboards/{id}/assets/{asset_id}/generate-image` |
| 分镜批量生成 | `POST /api/shots/storyboards/{sid}/projects/{id}/generate` |
| 单场分镜生成 | `POST .../scenes/{scene_id}/generate-scene-shot` |
| 单场分镜图 | `POST .../scenes/{scene_id}/generate-grid` |
| 分集视频自动分片（含批量出片） | `POST .../video-items/auto-generate-segments` |
| 单条分集视频 | `POST .../video-items/{item_id}/quick-generate` |

**不扣费**：素材库全部目录操作（`/api/folders`、`GET /api/media/{id}`）、审核素材库全部操作（`/api/review-assets`，但占配额）、`POST /api/upload`、所有查询类接口、`POST /api/prompts/generate`（提示词润色，文档未标 `InsufficientBalance`）。

**文档未说明**的：建项目、存剧本、`extract-assets`、建分镜项目、分镜导入 preview/apply、建 video-items、导出。这些页面的返回码里没有 `InsufficientBalance`。按不扣费处理，但**不要向用户打包票说"这步免费"**——说"这一步不涉及生成，通常不扣费"。

## 一个容易踩的坑

**资产参考图：1 个请求 = 1 张图 = 计 1 次费。** 要 16 张就要发 16 个独立请求，扣 16 次。批量之前务必告诉用户总数和总预估。

图片统一入口同理：每次请求生成一张，要多张就多次提交。

## 预估怎么算

见 [models.md 的「成本预估」](./models.md#成本预估重要)。要点：`resolution_prices` 非 `null` 时按分辨率取价并**覆盖**顶层 `unit_price`，然后按 `billing_unit` 乘数量。

## Pre-Submit 话术

提交任何扣费任务前，用一句话讲清三件事——**要花多少、停不下来、花的是团队的钱**：

> 准备生成 3 条 8 秒 1080p 视频，预估约 6240 积分（从团队账户扣）。任务提交后无法中止。确认开始吗？

用户确认后再发请求。**默认必须确认**；只有用户明确说过"后面都不用问我"才可以连续提交，但每个阶段结束仍要报一次实际用量。

## 余额不足了怎么办

收到 `InsufficientBalance`：

- 如实告诉用户余额不足，需要在控制台充值。
- **不要重试**，不要降配偷偷再试一次。
- 如果是多条任务跑到一半才不足，把「已完成 / 未提交」的分界说清楚，并确认状态文件已记录，好让用户充值后能续跑。

收到 `QuotaExceeded.MemberMonthlyCredits`：团队管理员给这位成员设了月度积分上限并已用完。这不是充值能解决的，要找管理员调额度。

## 账单查询

`GET /api/billing/storyboards`（短剧消耗列表）和 `GET /api/billing/storyboards/{id}/dimensions`（图片/视频/剧本/分镜四维度构成）**仅团队 Owner 可访问**。如果 API Key 代表的成员不是 Owner，会返回 `Forbidden`——这不是 bug，不要重试。
