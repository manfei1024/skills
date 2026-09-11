# Changelog

本技能包版本跟随 Click 对外 API 契约。接口路径、必填参数、扣费口径、`auto-produce` 阶段枚举、`model-list` 字段语义发生变化时发新版本。

格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.1.0-rc.3] - 2026-09-11

### Changed

- **Breaking**：仓库来源从 `AI-Hub-Growth/skills` 迁移到 `manfei1024/skills`。Marketplace/插件名 `aicanvas` → `click`，插件 id `aicanvas@aicanvas` → `click@click`，三个技能改名 `click-drama` / `click-media` / `click-assets`。
- 环境变量 `AICANVAS_HOST` / `AICANVAS_API_KEY` → `CLICK_HOST` / `CLICK_API_KEY`；`API Key` 前缀 `cak_` 不变。
- 默认 Host 改为 `https://click.vibehub.art`。
- 旧版 `aicanvas@aicanvas` 用户需卸载重装，并按新变量名重新配置 `CLICK_HOST` / `CLICK_API_KEY`。

## [0.1.0-rc.2] - 2026-08-20

### Added

- 新增与 Canvas 单场景分镜编辑器一致的分镜 DSL 说明：镜头标记、九个固定字段、多行转义、中文候选值、`@` 素材引用、时长格式和默认导入示例。
- 三个 skill 每次运行前共同检查仓库 `main` 版本；无法确认版本时停止，发现不一致时通过 Codex / Claude Code 插件管理器更新。

### Fixed

- 修正参考素材流程：生成只消费 URL，`POST /api/media` 是可选的素材管理步骤；平台上传 URL 使用 `source=uploaded`，外部 URL 仅在用户明确要求入库时使用 `source=imported`，并作为可能变化或失效的外链引用管理。

## [0.1.0-rc.1] - 2026-08-11

首个版本。

候选版发布前统一产品英文名为 Click、中文名为 Click；插件与三个 skill、环境变量、状态文件和辅助脚本均使用 `click` / `CLICK_*` 命名，不保留未发布旧名称的兼容别名。

### Added

- `click-drama` —— 整部短剧制作。一键链路（`POST /api/storyboards/auto-produce`）与分步链路（建项目 → 剧本 → 资产 → 参考图 → 分镜项目 → 分镜 → 分集视频 → 导出）双路径，含分镜导出/编辑/preview/apply 往返流程。
- `click-media` —— 单张图片（`POST /api/ai/image/task`）、单条视频（`POST /api/ai/video/task`）、提示词润色（`POST /api/prompts/generate`）。
- `click-assets` —— 素材库目录与资产管理、审核素材库合规预审核。
- `plugins/click/common/` 共享规则：`auth.md`、`models.md`、`billing.md`、`async-tasks.md`、`errors.md`、`upload.md`、`api-index.md`。
- 共享 HTTP/状态脚本：校验 HTTPS Host、拒绝跨域与重定向、检查 HTTP/业务错误、原子记录任务类型和轮询路径。
- Claude Code 与 Codex marketplace 清单，插件实体位于标准 `plugins/click/` 布局。
- 安装文档：`INSTALL.md`（给人看）、`INSTALL_FOR_AGENTS.md`（给 agent 看）。
- CI 校验 `scripts/validate.py`：frontmatter、链接与锚点、manifest、恢复契约、版本一致性、明文密钥和生成文件检测；附共享脚本离线单测。

### 已知限制

- **并发上限、单次批量条数上限平台未公开**。技能包写了保守默认（批量不超过 3 并发），遇 `UpstreamError.RateLimited` 退避重试。
- 不覆盖无对外文档的能力：TTS、LLM chat、composition、legacy 图片接口。
- HTTP 提交与本地状态不能组成跨系统事务；提交结果不明确时默认禁止自动重发，并先通过读取接口对账。
- Cursor 安装尚未实装验证；首版正式支持 Claude Code 与 Codex。

[0.1.0-rc.1]: https://github.com/manfei1024/skills/releases/tag/v0.1.0-rc.1
[0.1.0-rc.2]: https://github.com/manfei1024/skills/releases/tag/v0.1.0-rc.2
[0.1.0-rc.3]: https://github.com/manfei1024/skills/releases/tag/v0.1.0-rc.3
[Unreleased]: https://github.com/manfei1024/skills/compare/v0.1.0-rc.3...HEAD
