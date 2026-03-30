# 架构说明

## 分层

依赖方向固定为：

`WebUI -> Agent Orchestration -> Tool -> Workflow -> Service -> Infrastructure`

### WebUI

正式入口是独立 `React + Vite + TypeScript` 工作台。前端负责会话交互、SSE 消费、Workbench 展示和 Debug Drawer，不承载领域逻辑。

### Agent Orchestration

第一阶段采用单一 `ReAct` 模式，不引入 Planner。

当前由以下模块组成：

- `AgentRuntime`
  单个 `PydanticAI Agent`，负责直接回复或调用 workflow-level tools
- `ContextManager`
  组装消息窗口、最近任务、最近报告和当前会话 source
- `MemoryManager`
  当前实现短期和中期记忆
- `Event Stream`
  推送 `run_started / tool_called / tool_result / assistant_* / run_* / session_snapshot`

### Tool

只向 Agent 暴露 workflow-level tools：

- 文件分析
- 数据库分析
- 加载最近报告
- 概括最近报告

### Workflow

负责把多个 `Service` 步骤可靠串联，维护产物传递、失败终止和结构化结果。

### Service

负责领域业务能力抽象。当前仍由 `StubAnalysisPlatform` 提供可运行假实现，后续替换为 QT 适配实现。

### Infrastructure

当前包含：

- SQLite：session、task、run、run step、source、artifact 持久化
- 本地 artifact 落盘

## 当前实现原则

- `TaskApplicationService` 只负责任务状态、结果和产物持久化
- 具体执行由 `AnalysisExecutionService` 调用 `WorkflowToolRegistry`
- Agent 分析能力必须建立在会话级 source 上，不允许 runtime 内置 demo 文件或固定 SQL
- demo 通过显式 `demo source` helper API 注入
- `llm` 模式模型失败时，在同一 run 内回退到 `fake`
- 长期记忆、RAG、Planner 保留为后续扩展位，不在第一阶段实现
