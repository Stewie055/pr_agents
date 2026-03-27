# REQUIREMENTS

## 目标

把现有 QT 数据可视化和分析程序改造成 Agent 可调用的平台能力，对外提供可编排、可测试、可扩展的分析流程。

## 关键要求

- 保持六层架构分层清晰。
- `PydanticAI` 只承担 Agent 和 Tool 的轻量承接。
- 领域业务只进入 `Service` 和 `Workflow`。
- 所有真实业务必须通过 `business_code` 显式标识。
- 支持 A 类单业务单文件和 B 类多业务共享文件两种来源模式。
- 支持文件分析、数据库分析、图表生成、报告生成。
- 支持用户通过聊天式 WebUI 使用 Agent 发起分析任务。
- 支持 Agent session、多轮消息和 Agent 过程可视化。
- 支持基础会话恢复和任务结果恢复。
- Agent 的自然语言理解与工具决策需要独立于具体 session 控制逻辑。
- 必须同时保留 `fake` 和 `llm` 两种模型模式。
- 业务 `Service` 适配阶段默认应可使用 `fake` 模式，业务调通后再切换 `llm`。
- `llm` 模式当前默认接入 GLM 官方 API，并默认使用 `GLM-4.5-Air`。
- LLM provider 必须有独立适配层，便于后续把代码迁移到局域网环境后替换为其他网关或模型。
- LLM API key 只允许通过环境变量或本地未提交配置注入，不得写入仓库。
- Agent 必须采用“对话优先、工具后置”的交互原则，但是否调用工具由 LLM 的结构化决策决定，不由 runtime 预先写死分支。
- Agent Orchestration 需要以单一 `AgentRuntime` 为主入口，内部使用单个 `PydanticAI Agent` 作为执行主体。
- 运行时上下文必须由 `ContextManager` 和 `Memory` 提供，不允许把会话判断、业务分流、工具参数拼装散落在 session 层。
- Agent 只允许调用白名单 workflow-level tools，不直接暴露 Service 级能力。
- `Memory` 是 Agent Orchestration 的正式一层，当前至少包含短期和中期记忆；长期知识和 RAG 归属于 Memory 的后续扩展能力。
- 任务型消息必须保留 run/plan/step 轨迹，并支持失败后保留轨迹停止。
- WebUI 需要支持 SSE 流式事件，而不是等待整包执行结果。
- 流式协议应采用“POST 创建 run + GET SSE 订阅”的方式。
- 工具型请求应先展示工具/步骤卡片，再在流程完成后输出 assistant 回复。
- 直接回复型请求应通过 assistant 文本流增量输出，而不是等待完整回复后一次性展示。
- WebUI 当前采用独立 `React + Vite + TypeScript` 前端工程承接聊天式交互。
- WebUI 当前信息架构固定为：
  - 左侧 `Chat Panel`
  - 右侧 `Workbench`
  - 右侧默认收起的 `Debug Drawer`
- 聊天区只展示用户/assistant 对话和轻量工具状态。
- 表格、图表、报告预览必须优先进入 `Workbench`。
- 调试信息通过 `Debug Drawer` 展示，第一阶段只读，默认弱化存在感。
- 图表产物需要提供可直接渲染的原始资源接口，当前 stub 统一输出 `SVG`。
- 前端必须补齐自动化测试，至少覆盖组件渲染、布局结构和关键交互。
- 官方 demo 至少应覆盖两条主线：文件分析和数据库分析，并支持报告重看与报告摘要追问。
- 支持 HTTP 任务提交、任务查询、会话任务查询和产物读取。
- 所有输入输出使用统一数据模型。
- 所有流程都必须有结构化结果和错误返回。
- 任务元数据和产物元数据必须可持久化到 SQLite。
- matplotlib 自定义科学绘图必须作为统一图表产物的一种类型承接。
- 能以 stub 实现先跑通，再由人工替换成 QT 能力。

## 非目标

- 本仓库不直接承载 QT 源码。
- 当前版本不追求真实建模算法。
- 当前版本不实现长期记忆和真实 RAG 检索，仅保留 Memory 内的扩展接口位置。
