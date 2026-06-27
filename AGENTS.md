# Codex 项目规则

进入项目后依次读取：

1. `C:\Users\admin\AGENT_SHARED_CONTEXT.md`
2. `PROJECT_CONTEXT.md`
3. `STATUS.md`
4. 本文件
5. `PRD.md` 等按需文档

## 工作规则

- 当前用户是达达。
- 项目模式：`standard`。
- 项目长期事实只写入 `PROJECT_CONTEXT.md`。
- 当前任务状态只写入 `STATUS.md`。
- 当前 Agent 能完成时直接继续；只有工具或能力确有差异时才建议切换。
- 同一时间只允许一个 Agent 修改本项目。
- 修改后运行与风险匹配的验证，并在结束前更新 `STATUS.md`。
- 不覆盖未知的用户改动，不使用破坏性 Git 命令。
- 禁止批量删除，包括通配符、递归、循环或一次删除多个路径。
- 只能使用 `Remove-Item -LiteralPath <一个明确路径>` 一次删除一个文件。
- 若需删除多个文件，立即停止并提示达达手动操作。
- 不在仓库中保存密码、Token、私钥或生产机密。

Agent 专属插件无法共享。Claude 缺少 Codex 已有插件或 Skill 时，提醒达达切换到
Codex 继续，反向同理。

## 统一口令

- `开始xxx，按工作流`：新项目初始化。
- `继续xxx，按工作流`：接着现有项目开发。
- `接手xxx，先读状态`：先读取项目状态文件再继续。
- Codex 和 Claude 都按同一套口令理解。
