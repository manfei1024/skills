# Click Agent Skills

在 codex / Claude Code 里用对话完成短剧制作，不用打开 Click 网页。

你说"把这个剧本做成 3 集短剧"，agent 自己查模型、算预估、提交任务、静默轮询、交付成片。

## 三个技能

| 技能 | 产物 | 什么时候用 |
|---|---|---|
| **click-drama** | 一部短剧（多集、成片） | "把这个剧本拍出来"、"做一部 5 集的"、"我的分镜表导进去出片" |
| **click-media** | 单张图 / 单条视频 | "画一张…"、"生成一段 5 秒的海浪"、"首尾帧做个转场" |
| **click-assets** | 素材库与合规预审核（不生成） | "把素材整理到文件夹"、"这几张图能过审吗" |

共享规则（鉴权、模型选型、计费、异步任务、错误处置、上传、接口索引）在 [`plugins/click/common/`](plugins/click/common/)，三个技能都指过去。

## 安装

见 [INSTALL.md](INSTALL.md)。给 agent 自己装的版本见 [INSTALL_FOR_AGENTS.md](INSTALL_FOR_AGENTS.md)。

普通用户只需要 API Key：

```bash
export CLICK_API_KEY="cak_..."     # 控制台「个人中心 → API Keys」创建
```

默认 API 地址是 `https://click.vibehub.art`。只有本地开发或私有部署才设置 `CLICK_HOST` 覆盖，例如 `http://127.0.0.1:8080`。

## 三件必须知道的事

1. **花的是团队账户的积分。** API Key 绑定团队，账单标记来源 `user_api_key`。
2. **平台没有中止接口。** 生成任务一提交就停不下来，也退不回来。
3. **平台没有查余额的接口。** 所以技能包里所有扣费操作都会**先算预估、先问你**，这是唯一的防线。

## 设计取舍

Click 没有 CLI 也没有 MCP server。技能包提供一个很薄的共享 HTTP/状态脚本，负责 Host 限制、错误检查和断线续跑；制片判断仍由 agent 按 **BLOCKING** 门执行：

- **模型 ID / 分辨率 / 画幅 / 时长必须来自 `GET /api/ai/model-list` 实时返回**，禁止硬编码
- **导入分镜必须先 `imports/preview`**，把 diff 给人核对过再 apply
- **批量出片前必须先单条试跑**
- **提交任何扣费任务前，报预估 + 拿确认**

模型选择、预览和用户确认属于文档纪律；请求安全、响应校验和恢复状态由共享脚本兜底。

每个 skill 开始工作前还会检查本地插件 manifest 是否与仓库 `main` 一致；版本不一致时先通过 Codex / Claude Code 的插件管理器更新，避免按旧接口或旧流程继续执行。

## 文档来源

所有接口路径、方法、必填参数都逐条对照 Click 的公开 API 文档站写成。**不参照已过时的 `api-summary.md`。**

已知缺口：平台未公开并发上限与单次批量条数上限，技能包按保守默认（同时不超过 3 个生成任务）处理。

## 版本

见 [CHANGELOG.md](CHANGELOG.md) 和 [VERSION](VERSION)。

## License

MIT，见 [LICENSE](LICENSE)。
