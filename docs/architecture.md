# 架构说明

## 分层

依赖方向固定为：

`WebUI -> Agent Orchestration -> Tool -> Workflow -> Service -> Infrastructure`

### WebUI

负责用户输入、任务发起、结果展示、会话视图，不承载领域逻辑。当前通过 `Vue + Vite` 的诊断工作台作为用户入口，FastAPI 托管构建产物，并通过 `SSE` 流式接收 Agent 运行事件。

### Agent Orchestration

负责管理 session、上下文、记忆、执行和事件流。当前 Agent 运行时以单一 `AgentRuntime` 为主入口，内部由以下模块组成：

- `AgentRuntime`
  统一承接用户消息、上下文装配、单个 `PydanticAI Agent` 的决策与工具调用、SSE 事件和 SQLite 持久化
- `ContextManager`
  从 session、message、task、artifact 和 memory 组装 `AgentContext`
- `Memory`
  当前实现短期与中期记忆；长期知识与 RAG 作为后续扩展位，归属于 Memory
- `Agent Tools`
  仅向模型暴露 workflow-level tools：文件分析、数据库分析、加载最近报告、概括最近报告
- `Event Stream`
  将 run 生命周期、步骤状态和关键 tool 结果通过 SSE 推给前端
- `Run Control`
  提供 run 级控制骨架，当前支持 `Pause / Resume` 状态切换，并记录 `Rerun Step / Modify State` 请求元数据

### Tool

向 Agent 暴露粗粒度、业务友好的调用入口，负责参数校验和调用 Workflow。

### Workflow

负责把多个 Service 步骤可靠串联，维护产物传递、失败终止和结构化结果。

### Service

负责领域业务能力抽象，是人工接入 QT 能力的唯一入口。当前接口采用 `business_code` 驱动的通用模式，由具体实现决定业务属于 A 类还是 B 类。

### Infrastructure

负责任务目录、产物保存、文件引用和底层存储适配。当前已包含本地 artifact 落盘和 SQLite 元数据存储。

## 当前实现原则

- 所有接口统一使用 Pydantic 模型。
- Workflow 负责可靠流程，Service 负责领域能力。
- Tool 不直接耦合 QT 实现。
- 当前使用 stub 实现跑通闭环，后续替换为真实适配器。
- 任务执行采用同步模式，但统一使用 `task_id` 和状态机模型，便于后续扩展异步执行。
- A 类“单业务单文件”和 B 类“多业务共享文件”不拆成两套 API，只通过 `business_code` 和 `source_profile` 区分。
- 普通图表和 matplotlib 科学绘图统一建模为 `ChartArtifact`。
- 用户 Demo 路径采用聊天式 Agent 会话：用户消息 -> Agent 计划 -> Tool 调用 -> 任务结果 -> 报告内容。
- 官方 demo 当前包含两条主线：文件入口分析和数据库入口分析；两者共享同一套 Router / Planner / Executor / Workflow 链路。
- 当前 Agent 会话层已将任务结果快照持久化到 SQLite 以支持重启恢复。
- 当前模型层支持双模：
  - `fake`：规则式稳定模式，由 `FakeLLM` 提供
  - `llm`：通过 `GLMProvider` 调用真实模型，失败自动回退到 `fake`
- GLM 官方 API 的 HTTP 调用被隔离在独立 provider 中，`AgentSessionService` 和 `AgentRuntime` 不直接依赖供应商细节。
- 默认模型配置为 `GLM-4.5-Air`，便于开发环境先验证自然语言理解；后续迁移到局域网环境时可只替换 provider 配置或实现。
- 工厂在启动时负责注入 fake 或真实 llm；AgentRuntime 只使用注入后的模型，不在上层散布分支。
- 单个 `PydanticAI Agent` 的决策决定是直接回复，还是调用 `load_latest_report`、`summarize_report`、`run_file_analysis_workflow`、`run_db_analysis_workflow` 等白名单 tools。
- 前端发送消息时采用“POST 创建 run + GET SSE 订阅”模式，而不是等待整包 JSON 响应。
- 前端的 `Execution Controls` 已接到后端 run control 接口；当前实现为协作式控制，优先在步骤边界和文本流边界生效。
- WebUI 展示层采用“左侧交流、右侧工作、调试抽屉弱化、底部状态栏固定”的工作台策略。
- 前端状态模型显式分为：
  - `workspaceState`
  - `processState`
  - `artifactState`
  - `debugState`
  - `statusBarState`
- 当前流式协议分为两类：
  - 工具与步骤事件流：先展示 tool / step 卡片
  - assistant 文本流：通过 `assistant_delta` 增量输出最终回复，而不是等完整 session 再一次性刷新
