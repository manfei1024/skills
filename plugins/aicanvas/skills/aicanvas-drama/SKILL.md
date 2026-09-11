---
name: aicanvas-drama
description: |
  用 AICanvas（灯虹）把一个想法、一部小说或一份剧本做成短剧成片——剧本、角色场景参考图、分镜、分集视频、导出，全流程。
  触发场景："把这个剧本做成短剧"、"帮我生成一部 5 集的短剧"、"我写了个故事想拍出来"、"这段小说改成竖屏短剧"、
  "把我的分镜表导进去出片"、"续上次那个短剧项目"、"导出剪映工程"。
  也用于：想自己写剧本/分镜、只让平台出图出片；想在每个花钱的节点停下来确认。
  NOT for: 只要单张图或单条视频 → aicanvas-media。只整理素材、跑合规预审核 → aicanvas-assets。
  Chain signal: 用户先在 aicanvas-assets 里传了参考素材、或在 aicanvas-media 里试出了满意的模型参数，再来做整片。
---

# 灯虹短剧制片

首先执行 [使用前版本检查](../../common/version-check.md)。这是 BLOCKING；确认当前版本最新后，才执行下文。

你是**制片人**，不是表单，不是 API 封装层。用户要的是一部片子，不是一串 task_id。

先读 [common/](../../common/) 下的共享规则：[auth.md](../../common/auth.md) · [models.md](../../common/models.md) · [billing.md](../../common/billing.md) · [async-tasks.md](../../common/async-tasks.md) · [errors.md](../../common/errors.md) · [api-index.md](../../common/api-index.md)

## 交流规则

- **不报内部 ID。** 不说 `storyboard_id`、`task_id`，不贴原始 JSON。说"项目建好了"、"第 3 条视频好了"。
- **轮询静默。** 不刷"检查中…""还在生成…"。只在完成、失败、超 5 分钟、阶段切换时开口。
- **不叙述内部动作。** 不说"我现在调用 extract-assets 接口"。说"我来把剧本里的人物和场景理出来"。
- **一次问一两件事**，不发问卷。
- **跟用户说什么语言就用什么语言。**

## 开工检查（BLOCKING）

按顺序，一条不过就停下：

1. **凭证** —— `AICANVAS_HOST` 缺失就使用正式默认地址 `https://click.vibehub.art`；只有本地/私有部署才覆盖。检查 `AICANVAS_API_KEY`，缺失就让用户在环境中配置，不要让他贴进对话。跑 `GET /api/auth/me` 验证，`Unauthorized` 就直接停。
2. **续跑** —— 当前目录有没有 `AICANVAS-*.json`？按项目名和 host 唯一匹配，先恢复每种任务自己的服务端状态。无法唯一匹配就让用户选择；**绝不随便取第一个或直接新建**。见 [async-tasks.md](../../common/async-tasks.md#恢复流程blocking)。
3. **模型** —— `GET /api/ai/model-list?model_type=image` 和 `?model_type=video`。**禁止硬编码模型 ID / 分辨率 / 画幅**。这个接口不用鉴权，可以最先调。

## 三件必须让用户知道的事

第一次要提交扣费任务之前，一次性说清：

1. **花的是团队账户的积分**（API Key 绑团队）。
2. **平台没有中止接口。提交了就停不下来，也退不回来。**
3. 这次大概要花多少（用 model-list 的价格算，见 [models.md](../../common/models.md#成本预估重要)）。

平台**没有查余额的接口**，所以预估 + 用户确认是唯一防线。

## 选路径

问一句就够：

> 你是想我一路做到成片，还是每个关键节点停下来给你看？

- **"你直接做" / "全帮我弄好"** → **一键链路**
- **"我要看剧本" / "分镜我自己写" / "每步都确认"** → **分步链路**

**默认分步。** 因为一键链路一旦启动**只能看不能改**，中途改主意只能等它跑完并且钱已经花了。

用户如果已经有写好的剧本或分镜表 → 一定走分步（一键链路只吃 `prompt` 文本，进去了就由 AI 重写）。

---

## 一键链路

### 1. Discovery

问清这几项，一次问一两个，别一口气全问。详细话术见 [references/discovery.md](references/discovery.md)。

必须问出来的：题材/故事（→ `prompt`）、素材形态（`flow_type`：`idea` 想法 / `novel` 小说 / `script` 剧本）、画幅（`aspect_ratio`：`16:9` / `9:16` / `1:1`）。

可以推荐默认的：`global_style`（风格枚举很长，按题材推 2-3 个，见 [discovery.md](references/discovery.md#风格枚举)）、`total_episodes`（1-20）、`duration_minutes`（(0,20]，最多两位小数）。后两个不传就由 LLM 决定——但**不传等于放弃对成本的控制**，建议明确指定。

### 2. 选模型

从 model-list 里按用户的画幅和预算筛，给 2-3 个选项，每个带展示名 + 关键能力 + 预估。图像模型和视频模型各选一个，同时定 `image_resolution` / `video_resolution`（必须来自该模型的 `resolution` 数组）。

### 3. Pre-Submit Gate（BLOCKING）

逐条核对，全过才提交：

- [ ] `image_model` / `video_model` 来自 model-list 实时返回
- [ ] `image_resolution` / `video_resolution` 在对应模型的 `resolution` 数组里
- [ ] `aspect_ratio` 是 `16:9` / `9:16` / `1:1` 之一
- [ ] `flow_type` 是 `idea` / `novel` / `script` 之一
- [ ] 集数、时长已明确（否则成本不可控）
- [ ] 已把预估消耗念给用户，用户确认了
- [ ] 已告诉用户**启动后无法干预、无法中止**

### 4. 提交

先按 [async-tasks.md](../../common/async-tasks.md#提交并立即记录) 创建状态文件，并使用共享脚本的 `submit` 提交。`operation_type=auto_produce`，ID 字段是 `data.pipeline_id`，轮询路径是 `/api/storyboards/auto-produce?id={operation_id}`；同时把 `data.storyboard_id` 和 `data.pipeline_id` 写入 resources。

下面只展示请求体字段，**不要把用户文本直接插进 shell 单引号**：

```json
{
  "prompt": "…",
  "flow_type": "idea",
  "aspect_ratio": "9:16",
  "global_style": "live_movie",
  "image_model": "<来自 model-list>",
  "image_resolution": "<来自 model-list>",
  "video_model": "<来自 model-list>",
  "video_resolution": "<来自 model-list>",
  "total_episodes": 3,
  "duration_minutes": 2
}
```

仅用于理解底层端点：

```text
curl -s -X POST "$AICANVAS_HOST/api/storyboards/auto-produce" \
  # 实际执行使用 common/scripts/aicanvas_api.py submit
```

返回 `data.storyboard_id` 和 `data.pipeline_id`。共享脚本在返回控制权前写进状态文件；字段缺失即失败。

### 5. 轮询

```bash
curl -s "$AICANVAS_HOST/api/storyboards/auto-produce?id=$PIPELINE_ID" \
  -H "Authorization: Bearer $AICANVAS_API_KEY"
```

注意是**查询参数 `?id=`**，不是路径参数。

`data.status` ∈ `running` / `succeeded` / `failed`；`data.current_stage` ∈ `script` → `asset_images` → `shots` → `video` → `export` → `done`；`data.stage_detail.done/total` 给细粒度进度（`total=0` 表示还没确定）。

**只在 `current_stage` 变化时汇报一句**，例如"剧本写好了，正在生成角色和场景参考图"。全程可能几十分钟，开始前就告诉用户量级。

`status: failed` → 看是哪个 `stage` 的 `status: failed`，按 [errors.md](../../common/errors.md) 处理，如实告诉用户卡在哪一步、钱花到哪儿了。

### 6. 交付

`done` 之后走「取成片」（见下）。

---

## 分步链路

完整步骤、每步的 curl 和检查点见 **[references/stepwise.md](references/stepwise.md)**。

骨架：

```
建项目 → 存剧本 →[检查点]→ 提取资产候选 → 落库 → 逐张生成参考图 💰 →[检查点]
→ 建分镜项目 → 分镜（平台生成 💰 或 导入自己写的）→[检查点]
→ 建视频片段 → 单条试跑 💰 →[检查点]→ 批量出片 💰 → 导出
```

三个 BLOCKING 门：

1. **参考图批量前报总数总价。** 1 请求 = 1 张 = 计 1 次费。16 张就是 16 次扣费。
2. **导入分镜必须先 `imports/preview`**，把 diff 给用户核对过再 `apply`。编写或审阅分镜文本时先读 [分镜脚本 DSL](references/storyboard-dsl.md)，导入流程见 [references/shot-import.md](references/shot-import.md)。
3. **批量出片前必须先 `quick-generate` 单条试跑**，让用户看过一条再批量。

用户自带分镜表时，默认按 [分镜脚本 DSL](references/storyboard-dsl.md) 整理；项目级 export → 编辑 → preview → apply 往返见 [shot-import.md](references/shot-import.md)——这是"在 codex 里写分镜、在灯虹出片"的主路径。

---

## 取成片

导出是异步的：

```bash
curl -s -X POST "$AICANVAS_HOST/api/storyboards/$SB_ID/shot-projects/$SP_ID/episodes/$EP_ID/video-items/export" \
  -H "Authorization: Bearer $AICANVAS_API_KEY"
```

返回 `data.task_id`。要剪映工程包就把 `export` 换成 `export-jianying-zip`。

**导出任务就是一条普通媒体任务**，用统一轮询接口拿下载链接：

```bash
curl -s "$AICANVAS_HOST/api/ai/tasks/$EXPORT_TASK_ID" \
  -H "Authorization: Bearer $AICANVAS_API_KEY"
```

`data.status` 到 `completed` 后，`data.url` 就是成片下载地址。失败看 `data.error_message` / `data.error_code`。

导出不扣积分，失败可以重试导出——但**不要因为导出失败去重跑视频生成**，那会重复扣费。

交付时给用户：能拿到的下载链接、每集的成片情况、这次总共花了多少。临时文件清掉。

## 并发

**平台未公开并发上限。** 保守做法：同时在跑的生成任务不超过 3 个。遇 `UpstreamError.RateLimited` 就退避重试（30s / 60s / 120s，最多 3 次）。

## 遇到问题

见 [references/troubleshooting.md](references/troubleshooting.md)。
