# REQUIREMENTS

## 目标

把现有 QT 数据可视化和分析程序改造成 Agent 可调用的数据分析工作台，对外提供可追踪、可测试、可扩展的分析能力。

## 第一阶段关键要求

- 产品定位为业务分析工作台，聊天只是任务入口。
- 第一阶段使用单一 `ReAct` Agent，不实现 Planner、多 Agent、长期记忆和 RAG。
- 使用 `PydanticAI` 承接 Agent loop 和 tool 注册，不承接领域业务。
- 数据源必须显式选择；未选择 source 时返回 clarification，不自动使用最新 source。
- 支持真实 CSV 上传，后端保存原始文件并生成 schema summary。
- 支持 SQL 表单注册，第一阶段不真实执行数据库，只由 stub 业务返回模拟查询结果。
- 固定业务码为 `file_analysis` 和 `db_analysis`，用于模拟真实 QT 业务适配。
- 支持后台异步分析任务，状态包含 `queued`、`running`、`succeeded`、`failed`、`cancelled`。
- 支持取消任务：queued 可直接取消，running 在 step 边界响应取消。
- 支持结构化报告、图表图片和表格 artifact。
- 支持 React WebUI 展示 source、会话、Agent 工具步骤、任务状态、图表、表格和报告。
- 支持 `fake` 和 `llm` 模型模式；默认 `fake`，真实模型失败回退到 `fake`。
- WebUI 使用 REST 创建资源，使用 SSE 订阅 Agent run 和任务事件。
- 任务、source、run、step、artifact 元数据必须持久化到 SQLite。
- 上传文件、图表图片、报告和表格 artifact 必须落盘到本地 artifact 目录。
- 每次新增功能必须补充自动化测试；如无法补齐，必须说明风险和补测计划。
- 每次修改必须同步更新 `README.md`、`REQUIREMENTS.md` 和 `docs/`。

## 非目标

- 本仓库不直接承载 QT 源码。
- 当前版本不实现真实业务算法和真实数据库查询。
- 当前版本不做鉴权、租户、权限、限流和生产级任务队列。
- 当前版本不做 Planner、多 Agent、长期记忆、RAG。
- 当前版本不要求兼容旧 demo 架构，但保留必要 API 兼容用于测试和演示。
