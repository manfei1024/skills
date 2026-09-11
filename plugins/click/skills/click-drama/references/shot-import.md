# 导入自己写的分镜

用户在 codex / 编辑器里写好分镜表，导进 Click 出片。**不扣费。**

这是"在 agent 里写、在 Click 出片"的主路径。

## 往返流程

```
GET  .../export?format=md      导出模板（没分镜时是空白模板）
     ↓  用户 / 你 编辑
POST .../imports/preview       只读，返回 diff + fingerprint + scene_versions
     ↓  ⏸ BLOCKING：diff 给用户核对
POST .../imports/apply         原子覆盖
```

前缀统一 `/api/shots/storyboards/$SB_ID/projects/$SP_ID`。

## 1. 先导出拿格式

镜头块的字段与语法见 [分镜脚本 DSL](storyboard-dsl.md)。项目级文件还需要精确的分集/场景标题来匹配目标场景，因此**仍要先导出一份当外壳模板**，不要凭空编场景标题。

```bash
curl -s "$CLICK_HOST/api/shots/storyboards/$SB_ID/projects/$SP_ID/export?format=md" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -o shots.md
```

`format` **必填**，`md` 或 `txt`。返回的是 `text/plain` 文件附件，**不是 JSON 外壳**——别拿 `.code` 去解析。

项目还没有分镜时，导出会**回退到剧本结构、给出空白场景模板**——正好就是要填的骨架。这是新项目的正确起手式。

按场号自然排序，按场景的分集分组，集号从场号前缀推出来。

## 2. 编辑

先读 [分镜脚本 DSL](storyboard-dsl.md)，再在导出的 `.md` 上改。要点：

- **UTF-8**，扩展名 `.md` / `.markdown` / `.txt`，**≤ 2 MiB**
- **不要改场景标题行**——匹配靠它。改了就匹配不上，那一场会被跳过
- 保留导出文件中已有镜头的数字标记；新增镜头使用 `+:`，镜头块的文本顺序就是应用后的顺序
- 空场景 = 清空该场现有镜头（是"清空"不是"忽略"）
- 想只改一场，就只留那一场；其他场不在文档里就不动它们
- 默认使用编辑器的中文字段值，不把 `full_shot`、`slow_push_in` 等存储层枚举写进分镜文本
- 会影响构图、动作、镜头、灯光、环境或声音的内容放进 `画面描述` / `视频内容`，不要放在 `备注`

## 3. Preview（BLOCKING）

```bash
curl -s -X POST "$CLICK_HOST/api/shots/storyboards/$SB_ID/projects/$SP_ID/imports/preview" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -F 'file=@shots.md;type=text/markdown'
```

只读，不改任何东西。

返回：

| 字段 | 用途 |
|---|---|
| `data.fingerprint` | apply 时原样提交 |
| `data.summary` | 分集/场景/镜头数 + 新增/删除/更新/重排数量 |
| `data.summary.applicable_scene_count` | 能应用到当前项目的场景数 |
| `data.diagnostics[]` | 文档级问题（格式错、匹配不上） |
| `data.scenes[].applicable` | 该场能不能应用 |
| `data.scenes[].shot_scene_id` | 匹配到的场景 |
| `data.scenes[].version` | apply 时用于并发校验 |
| `data.scenes[].diff` | `created` / `deleted` / `updated` / `reordered` |

**必须把 diff 讲给用户听再 apply。** 用人话，不贴 JSON：

> 这份分镜能对上 8 个场景。新增 34 个镜头，改了 6 个，删掉 2 个。有 1 场（"内景-地下室-黄昏"）在项目里找不到对应场景，会被跳过。确认应用吗？

**特别要点出来的**：`applicable=false` 的场景（会被跳过）、`deleted` 不为空的场景（会丢东西）、`diagnostics` 里的每一条。

`code: 0` 但 diagnostics 有内容是正常的——**格式和匹配问题走 diagnostics，不走错误码**。别看到 0 就当全 OK。

## 4. Apply

```bash
curl -s -X POST "$CLICK_HOST/api/shots/storyboards/$SB_ID/projects/$SP_ID/imports/apply" \
  -H "Authorization: Bearer $CLICK_API_KEY" \
  -F 'file=@shots.md;type=text/markdown' \
  -F 'fingerprint=<preview 返回的>' \
  -F 'scene_versions={"scene_001":"2026-07-16T08:00:00Z"}'
```

三个都必填。`file` 必须和 preview 时**完全同一份**。`scene_versions` 是 JSON 字符串，键为可应用场景 ID，值为 preview 返回的 `version`——从 `data.scenes[]` 里挑 `applicable=true` 的组装。

**原子操作**：文件或场景在 preview 之后变过 → 整次失败，不会部分写入。

返回 `data.applied_scene_count` / `data.applied_shot_count`。

## 报错

| code | 处理 |
|---|---|
| `Shot.ImportPreviewExpired` | 文件或场景版本变了。**重新 preview，把新 diff 再给用户确认一遍**。不能拿旧 fingerprint 硬试 |
| `Shot.GenerationInProgress` | 目标场景正在生成。等完成再导 |
| `MissingParameter.*` / `InvalidParameter.*` | 文件缺失、编码不是 UTF-8、格式不支持、超 2 MiB |
| `ResourceNotFound.*` | ID 不对或不属于当前团队 |

## 反面做法

- ❌ 跳过 preview 直接 apply —— apply 必须要 fingerprint 和 scene_versions，本来也跳不过去；真正的坑是**preview 完不给用户看就 apply**
- ❌ preview 拿到的 diff 只报个数字就 apply
- ❌ 凭空猜 markdown 格式往里塞。先导出
- ❌ `ImportPreviewExpired` 后拿旧 fingerprint 重试
