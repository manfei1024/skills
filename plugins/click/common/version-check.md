# 使用前版本检查

每次进入任一 Click skill，**第一步**都执行本检查；在检查完成前，不读取凭证、不查询模型、不恢复任务，也不调用业务接口。

## 检查（BLOCKING）

从当前 `SKILL.md` 所在位置解析插件根目录，用绝对路径运行：

```bash
python3 <插件根目录>/common/scripts/check_version.py
```

退出码：

- `0`：本地 manifest 与仓库 `main` 的 manifest 版本一致，可以继续。
- `10`：版本不一致，按下方对应宿主更新。
- 其他：无法确认版本。停止当前 Click 工作并报告错误；不得把网络失败当作“已经最新”。

直接读取仓库 `main` 分支 raw `SKILL.md`、没有本地插件目录时，先读取远端 manifest；读取成功即可继续，因为当前指令与版本来源同为 `main`。读取失败则停止。

## 更新

只使用宿主的插件管理器，不用 `curl | sh`，也不直接改插件缓存。

### Codex

```bash
codex plugin marketplace upgrade click
codex plugin list
```

确认 `click@click` 显示的版本等于检查器报告的 `main` 版本。

### Claude Code

```bash
claude plugin marketplace update click
claude plugin update click@click
claude plugin list --json
```

确认已安装版本等于检查器报告的 `main` 版本。

更新完成后，不得继续依赖本轮已加载的旧版 skill 内容。告诉用户重新加载插件（Claude Code 可用 `/reload-plugins`）并重新发起当前请求；Codex 重新开启该请求后再继续。更新失败则报告具体错误并停止。
