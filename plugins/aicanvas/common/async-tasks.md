# 异步任务与续跑

灯虹的生成任务不共用一种状态接口。**不能只记 task ID，也不能假设所有任务都能用 `/api/ai/tasks/{id}` 查询。**

## 任务类型与轮询地址

| `operation_type` | 任务 | 正确的 `poll_path` |
|---|---|---|
| `media_task` | 单图、单视频、资产图、quick-generate、导出 | `/api/ai/tasks/{task_id}` |
| `auto_produce` | 短剧一键链路 | `/api/storyboards/auto-produce?id={pipeline_id}` |
| `shot_generation` | 分镜生成 | `/api/shots/storyboards/{sid}/projects/{spid}/scene-tasks` |
| `episode_batch` | 分集批量出片 | `/api/storyboards/{sid}/shot-projects/{spid}/episode-video-tasks` |
| `review_asset` | 审核素材 | `/api/review-assets/{id}` |

每次提交都把**准确的相对轮询路径**写进状态文件；恢复时使用记录的 `poll_path`，不要重新猜。

## 使用共享执行脚本

`common/scripts/aicanvas_api.py` 统一处理 HTTPS Host、禁止重定向、JSON 编码、HTTP/业务错误、必需响应字段和原子状态写入。涉及 JSON 或扣费的请求优先使用它，不要临时拼 `curl -d`。

```bash
AICANVAS_API="<技能包根目录>/common/scripts/aicanvas_api.py"

# 普通查询；--expect 缺字段时直接失败
python3 "$AICANVAS_API" request GET "/api/ai/tasks/$TASK_ID" \
  --expect data.status
```

脚本只允许以 `/api/` 开头的相对路径，且只会把凭证发往经过校验的 Host：默认 `https://click.vibehub.art`，设置 `AICANVAS_HOST` 时使用覆盖值。它不会跟随重定向，也不会把 API Key 写进输出。

## BLOCKING：没有 stop 接口

平台不提供中止生成任务的接口。提交出去就停不下来，也不能撤销扣费。

- 提交前确认是唯一介入点。
- 用户中途说“不要了”时，如实说明任务停不掉；不要假装取消。
- 会话中断后先恢复服务端状态，绝对不要因为本地不确定就重新提交。

## 状态文件

在用户当前工作目录创建 `AICANVAS-<项目名>.json`。不要手写或用文本替换更新；使用脚本原子写入：

```bash
python3 "$AICANVAS_API" state-init \
  --file "AICANVAS-夏日便利店.json" \
  --project-name "夏日便利店"
```

状态文件只记录恢复所需的业务信息：

```json
{
  "schema_version": 1,
  "project_name": "夏日便利店",
  "host": "https://example.aicanvas.host",
  "current_stage": "video",
  "resources": {
    "storyboard_id": "sb_xxx",
    "shot_project_id": "sp_xxx",
    "episode_id": "ep_xxx"
  },
  "operations": [
    {
      "operation_id": "task_xxx",
      "operation_type": "episode_batch",
      "poll_path": "/api/storyboards/sb_xxx/shot-projects/sp_xxx/episode-video-tasks",
      "scope": {"episode_id": "ep_xxx"},
      "status": "submitted",
      "estimated_credits": "6240",
      "confirmation_hash": "sha256..."
    }
  ]
}
```

不记录 API Key、完整请求体、提示词或用户素材内容。`confirmation_hash` 只证明当时确认的参数与预估组合，不保存原文。

### 提交并立即记录

扣费提交使用 `submit`。它会校验响应 ID，并在正常返回给 agent 之前原子写入操作类型和轮询地址：

```bash
python3 "$AICANVAS_API" submit POST "/api/ai/image/task" \
  --state "AICANVAS-夏日便利店.json" \
  --operation-type media_task \
  --id-field data.id \
  --poll-path '/api/ai/tasks/{operation_id}' \
  --scope '{"kind":"image"}' \
  --estimated-credits 120 \
  --json-file /tmp/aicanvas-image-request.json
```

请求 JSON 应放在权限受控的临时文件中，提交后删除；不要把复杂用户文本插入 shell 引号。

### 提交结果不明确时（BLOCKING）

HTTP 请求和本地状态文件无法组成真正的跨系统事务。进程可能在“服务端已经受理、客户端还没收到 ID”这个极小窗口中断。出现超时、连接断开、进程被杀或脚本没有正常返回时：

1. **禁止立即重发扣费请求。**
2. 先查询项目级任务列表、素材库或账单等现有公开读取接口，尝试识别刚提交的任务。
3. 能唯一识别时，把它补记进状态文件后继续轮询。
4. 单次媒体任务如果没有公开列表接口、无法唯一找回，就明确告诉用户处于“可能已提交”的不确定状态；等待结果在素材库出现或由用户决定是否承担重复扣费风险。默认不重发。

共享脚本能缩小这个窗口，但不能声称完全消除它。

一键链路可同时保存项目资源：

```bash
python3 "$AICANVAS_API" submit POST "/api/storyboards/auto-produce" \
  --state "AICANVAS-夏日便利店.json" \
  --operation-type auto_produce \
  --id-field data.pipeline_id \
  --resource storyboard_id=data.storyboard_id \
  --resource pipeline_id=data.pipeline_id \
  --poll-path '/api/storyboards/auto-produce?id={operation_id}' \
  --scope '{"kind":"full_drama"}' \
  --estimated-credits 10000 \
  --json-file /tmp/aicanvas-auto-produce.json
```

### 恢复流程（BLOCKING）

1. 查找当前目录的 `AICANVAS-*.json`。
2. 若有多个文件，根据用户说的项目名和 `host` 匹配；不能唯一匹配就让用户选择，**不能随便取第一个**。
3. 用 `pending --file ...` 列出非终态操作。
4. 对每项调用它记录的 `poll_path`，并读取对应任务类型的状态字段。
5. 再查询项目/分集的当前服务端状态，确认本地记录没有落后。
6. 使用 `update-operation` 补终态，再从 `current_stage` 继续。
7. 只有服务端明确不存在相同任务、状态文件也无已提交操作，才允许再次提交。

```bash
python3 "$AICANVAS_API" pending --file "AICANVAS-夏日便利店.json"
python3 "$AICANVAS_API" update-operation \
  --file "AICANVAS-夏日便利店.json" \
  --operation-id task_xxx \
  --status completed
```

## 轮询纪律

- 前 2 分钟每 10 秒一次，之后每 30 秒一次。
- 只在完成、失败、超过 5 分钟或多阶段任务切换时开口。
- `UpstreamError.RateLimited` 可按 30/60/120 秒退避；**重试查询，不是重新提交生成。**
- 查询失败或响应缺字段时停下诊断，不能据此认定原任务不存在。

## 失败处理

终态失败时看稳定错误码：

- `UpstreamError.ContentRejected`：不要重试，建议修改内容。
- `UpstreamError.ProviderUnavailable`：可在确认原任务已终态失败后重试一次。
- `UpstreamError.InvalidRequest` / `RequestRejected`：不要重试，检查参数。
- `InsufficientBalance`：不要重试，记录已完成与未提交的边界。

完整错误码见 [errors.md](./errors.md)。
