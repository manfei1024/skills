# 模型选型

## 唯一数据源

```bash
curl -s "$CLICK_HOST/api/ai/model-list"
```

**无需鉴权，可匿名调用。** 可以在向用户要 API Key 之前就先查。

按类型过滤：

```bash
curl -s "$CLICK_HOST/api/ai/model-list?model_type=video"
```

`model_type` 可选 `image` / `video` / `llm` / `audio`；不传返回全部已生效模型。

## BLOCKING：禁止硬编码

**模型 ID、分辨率、宽高比、时长、参考图数量，全部必须来自本接口的实时返回。**

- ❌ 不许凭记忆写模型 ID（模型会上下线、改名、改价）
- ❌ 不许把示例里的 `doubao-seedance-2-0-260128`、`kling-v3-omni` 当成一定存在
- ❌ 不许猜分辨率档位（有的模型是 `720p`/`1080p`，有的是 `1K`/`2K`，MiniMax-H3 是 `2k`/`768p`，还有的用绝对尺寸 `720x1280`）
- ✅ 每次会话开始时查一次，从返回结果里挑

生成接口对不在列表里的模型直接报 `InvalidParameter.Model`——`model_list` 中无 active 行的模型即视为不支持。

## 字段速查

| 字段 | 用途 |
|---|---|
| `model_id` | 提交生成任务时填进 `model` 的值 |
| `name` | 给用户看的展示名，别把 `model_id` 念给用户听 |
| `model_type` | `image` / `video` / `llm` / `audio` |
| `gen_modes` | **模式能力的唯一来源**，见下 |
| `aspect_ratio` | 支持的画幅数组；**空数组 = 不支持独立设画幅，必须省略该字段** |
| `resolution` | 支持的分辨率档位数组；**空数组 = 必须省略该字段** |
| `duration` | `{min, max}` 秒，仅视频；`null` = 不适用 |
| `max_reference_images` | 参考图上限；`0` = 不支持参考图 |
| `max_reference_videos` / `max_reference_audios` | `0` = 明确关闭，`null` = 未配置限制 |
| `unit_price` | 基础积分单价 |
| `billing_unit` | `image` 每张 / `second` 每秒 / `token` 每 token / `request` 每次 |
| `resolution_prices` | 按分辨率计价数组；非空且匹配到时**覆盖** `unit_price` |
| `review_asset_enabled` | `true` 时该模型的参考素材要先走审核素材库，见 [click-assets](../skills/click-assets/SKILL.md) |

## gen_modes

模式能力只认这个字段，不要从"有没有传参考图"反推。

图片：
- `text_to_image` —— 不需要参考图
- `image_to_image` —— 至少 1 张参考图，上限看 `max_reference_images`

视频：
- `text_to_video` —— 不需要参考图
- `image_to_video` —— 单张参考图
- `multi_ref_to_video` —— 多张参考图，上限看 `max_reference_images`
- `start_end_to_video` —— 首帧 + 尾帧各 1 张

非空数组 = 只允许声明的模式。空数组 = 未声明：视频兼容路径可视为不施加模式限制，但**图片模型必须明确声明**，空数组不能推断为无限制。

## 成本预估（重要）

**平台没有"查积分余额"的对外接口。** `GET /api/quotas` 只返回审核素材库的容量上限，不是钱包余额。所以**无法在提交前预检余额**——只能靠提交时返回 `InsufficientBalance` 才知道不够。

因此：**提交扣费任务前，用 model-list 的价格自己算出预估消耗，念给用户听，让他确认。** 这是唯一能防止意外扣费的手段。

算法：

1. 取该模型的 `resolution_prices`；非 `null` 就按用户选的 `resolution` 找对应项的 `unit_price`（大小写不敏感），找到就用它；`resolution_prices` 为 `null` 才用顶层 `unit_price`。
2. 按 `billing_unit` 乘数量：
   - `image` → 单价 × 张数
   - `second` → 单价 × 时长秒数 × 条数
   - `request` → 单价 × 请求次数
3. 多阶段任务（短剧）把各阶段加起来。

举例：视频模型 `billing_unit=second`，`resolution_prices` 里 `1080p` 单价 260，生成 3 条 8 秒视频 → `260 × 8 × 3 = 6240` 积分。

预估要说"大约"——实际扣费以平台结算为准，失败的任务是否退费本文档不做承诺。

## 选型时问用户什么

不要把整个模型列表甩给用户。按需求筛完再给 2-3 个选项，每个带上 **展示名 + 关键能力 + 预估消耗**。

例："画幅 9:16、1080p 的话有两个选择：A（约 2080 积分）画质更细腻；B（约 1200 积分）更快更省。用哪个？"
