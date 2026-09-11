# 安装

## 1. 拿 API Key

只能在 Click**控制台网页**创建：**个人中心 → API Keys → 新建**。

- 需要**团队所有者（owner）或管理员（admin）**身份，普通成员看不到入口
- 明文只在创建和重置时显示一次，**当场存好**
- 格式：`cak_` + 48 位十六进制

丢了就去控制台重置（regenerate），旧的立即失效。

## 2. 设 API Key

```bash
export CLICK_API_KEY="cak_..."
```

默认请求 `https://click.vibehub.art`，普通用户不用设置 Host。本地运行 canvas 时覆盖为 `export CLICK_HOST="http://127.0.0.1:8080"`。5173 是 Vite 前端及浏览器入口；虽然会代理 `/api`，Skill 的 API 测试应直连 8080。

写进 `~/.zshrc` / `~/.bashrc` 或用你惯用的密钥管理工具。**不要提交到 git。**

## 3. 装技能包

如果之前测试过旧名称，先卸载 `linc@linc`、移除旧 marketplace，再重新添加仓库；本候选版不保留旧名称兼容入口。新插件标识是 `click@click`。

### Claude Code

**方式 A：插件市场**

```
/plugin marketplace add manfei1024/skills
/plugin install click@click
```

### Codex

```text
codex plugin marketplace add manfei1024/skills
codex plugin add click@click
```

### Cursor

```bash
git clone --depth 1 https://github.com/manfei1024/skills.git ~/.cursor/skills/click
```

Cursor 的递归 skill 发现尚未纳入本版实装验证；正式支持范围目前是 Claude Code 和 Codex。

### 不装也能用

把某个 SKILL.md 的 raw 链接直接丢给 agent 让它读：

```
https://raw.githubusercontent.com/manfei1024/skills/main/plugins/click/skills/click-drama/SKILL.md
```

它会顺着相对链接找到 `common/` 和 `references/`。适合临时试用。

## 4. 验证

装完在 agent 里说一句：

> 用 Click 查一下有哪些可用的视频模型

预期行为：agent 调 `GET /api/ai/model-list?model_type=video`（这个接口不用鉴权），列出模型的展示名、支持的分辨率/画幅/时长和大致价格。

再验一次鉴权：

> 帮我确认下 Click 的 API Key 能用

预期：agent 调 `GET /api/auth/me`，返回身份信息就是通的。

手动验：

```bash
curl -s "${CLICK_HOST:-https://click.vibehub.art}/api/auth/me" -H "Authorization: Bearer $CLICK_API_KEY"
curl -s "${CLICK_HOST:-https://click.vibehub.art}/api/ai/model-list?model_type=video"
```

第一条返回 `Unauthorized` → 密钥无效、过期或已停用，去控制台重置。

## 5. 路由检查

分别说这三句，看 agent 选中的技能对不对：

| 你说 | 应该选中 |
|---|---|
| "生成一段 5 秒的海浪视频" | `click-media` |
| "把这个剧本做成 3 集短剧" | `click-drama` |
| "把这些素材整理进一个文件夹" | `click-assets` |

## 权限说明

API Key 代表**签发它的那位团队成员**。能做什么 = 那位成员用网页登录能做什么。认证方式变了，授权规则没变。

以下路径 API Key 一律拒绝，必须去控制台操作：`/api/user/**`、`/api/team/**`、`/api/admin/**`。

账单查询接口（`/api/billing/**`）**仅团队 Owner** 可用。

## 常见问题

**「Unauthorized」** —— 密钥无效/过期/停用，或成员被移出团队。去控制台重置。

**「Forbidden」** —— 碰了控制台专属路径，或成员角色不足，或账单接口非 Owner。不是 bug，别重试。

**「InsufficientBalance」** —— 团队积分不足，去控制台充值。

**「QuotaExceeded.MemberMonthlyCredits」** —— 管理员给这位成员设了月度上限并已用完。**充值解决不了**，找管理员调额度。

**agent 说模型不存在** —— 模型会上下线。让它重新查 `model-list`，别用记忆里的 ID。
