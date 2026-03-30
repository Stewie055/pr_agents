# REQUIREMENTS

## 目标

把现有 QT 数据可视化和分析程序改造成 Agent 可调用的平台能力，对外提供可编排、可测试、可扩展的分析流程。

## 第一阶段关键要求

- 保持六层架构分层清晰。
- 第一阶段 Agent 采用单一 `ReAct` 模式，不实现 `Planner` 分层。
- `PydanticAI` 只承担 Agent 和 Tool 的轻量承接。
- 领域业务只进入 `Service` 和 `Workflow`。
- 所有真实业务必须通过 `business_code` 显式标识。
- 支持 A 类单业务单文件和 B 类多业务共享文件两种来源模式。
- 支持文件分析、数据库分析、图表生成、报告生成。
- 支持用户通过 React WebUI 使用 Agent 发起分析任务。
- 支持 Agent session、多轮消息、source 注册和 Agent 过程可视化。
- 支持基础会话恢复和任务结果恢复。
- 必须同时保留 `fake` 和 `llm` 两种模型模式。
- `llm` 模式模型失败时必须自动回退到 `fake`；业务工具失败不做模型回退。
- Agent Orchestration 需要以单一 `AgentRuntime` 为主入口，内部使用单个 `PydanticAI Agent` 作为执行主体。
- 运行时上下文必须由 `ContextManager` 和 `Memory` 提供。
- Agent 只允许调用白名单 workflow-level tools，不直接暴露 Service 级能力。
- `Memory` 当前至少包含短期和中期记忆。
- WebUI 需要支持 SSE 流式事件，而不是等待整包执行结果。
- 流式协议采用“POST 创建 run + GET SSE 订阅”。
- 文件和数据库分析请求必须依赖显式 session source；不允许 runtime 内置 demo 输入。
- 官方 demo 必须通过显式 `demo source` 注入保留。
- WebUI 当前采用独立 `React + Vite + TypeScript` 前端工程承接聊天式交互。
- 前端必须补齐自动化测试，至少覆盖组件渲染、关键状态和构建。
- 支持 HTTP 任务提交、任务查询、会话任务查询、source 查询和产物读取。
- 所有输入输出使用统一数据模型。
- 任务元数据和产物元数据必须可持久化到 SQLite。
- 能以 stub 实现先跑通，再由人工替换成 QT 能力。

## 非目标

- 本仓库不直接承载 QT 源码。
- 当前版本不追求真实建模算法。
- 当前版本不实现长期记忆和真实 RAG 检索。
- 当前第一阶段不实现 Planner、复杂任务树和多 Agent 编排。
